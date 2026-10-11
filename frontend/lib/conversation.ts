import { api, getToken } from "./api";

export type Correction = {
  original: string;
  corrected: string;
  kind:
    | "grammar"
    | "tense"
    | "spelling"
    | "vocabulary"
    | "collocation"
    | "word_order"
    | "pragmatics";
  explanation_zh: string;
};

export type Scenario = {
  id: number;
  level: string;
  theme: string;
  title_en: string;
  title_zh: string;
  description_zh: string | null;
  goal: string;
  opening_line: string;
  recommended_words: string[];
  difficulty: number;
};

export type ChatMessage = {
  id?: number;
  conversation_id?: number;
  role: "user" | "assistant" | "system";
  content: string;
  has_error?: boolean | null;
  corrections?: Correction[];
  better_version?: string;
  hint_zh?: string;
  model_validated?: boolean | null;
  created_at?: string;
};

export type Conversation = {
  id: number;
  scenario_id: number;
  level: string;
  theme: string | null;
  title_en: string;
  title_zh: string;
  status: "active" | "finished";
  turn_count: number;
  report: ConversationReport | null;
  started_at?: string;
  ended_at?: string | null;
  scenario?: Scenario | null;
};

export type ConversationReport = {
  total_sentences: number;
  error_sentences: number;
  correction_count: number;
  kind_counts: Record<string, number>;
  accuracy: number | null;
  corrections: Correction[];
  teacher: {
    encouragement_en: string;
    encouragement_zh: string;
    next_tips: string[];
  };
};

export type ReviewItem = {
  id: number;
  source_conversation_id: number | null;
  item_kind: string | null;
  kind_zh?: string;
  title: string | null;
  original: string;
  corrected: string;
  explanation_zh: string | null;
  context_sentence: string | null;
  is_resolved: boolean;
  created_at?: string;
};

export const KIND_LABEL: Record<string, string> = {
  grammar: "语法",
  tense: "时态",
  spelling: "拼写",
  vocabulary: "用词",
  collocation: "搭配/介词",
  word_order: "语序",
  pragmatics: "语境表达",
};

export const KIND_COLOR: Record<string, string> = {
  grammar: "bg-rose-50 text-rose-600 border-rose-100",
  tense: "bg-orange-50 text-orange-600 border-orange-100",
  spelling: "bg-amber-50 text-amber-700 border-amber-100",
  vocabulary: "bg-blue-50 text-blue-600 border-blue-100",
  collocation: "bg-purple-50 text-purple-600 border-purple-100",
  word_order: "bg-indigo-50 text-indigo-600 border-indigo-100",
  pragmatics: "bg-teal-50 text-teal-600 border-teal-100",
};

export function listScenarios() {
  return api<{ scenarios: Scenario[] }>("/scenarios");
}

export function startConversation(scenarioId: number) {
  return api<Conversation>("/conversations", {
    method: "POST",
    body: JSON.stringify({ scenario_id: scenarioId }),
  });
}

export function listConversations() {
  return api<{ conversations: Conversation[] }>("/conversations");
}

export function getConversation(id: number) {
  return api<{ conversation: Conversation; messages: ChatMessage[] }>(
    `/conversations/${id}`,
  );
}

export function finishConversation(id: number) {
  return api<{ report: ConversationReport }>(`/conversations/${id}/finish`, {
    method: "POST",
  });
}

export function saveAllReviewItems(id: number) {
  return api<{ count: number }>(`/conversations/${id}/review-items`, {
    method: "POST",
    body: JSON.stringify({ save_all: true }),
  });
}

export function saveOneReviewItem(
  conversationId: number,
  messageId: number,
  correctionIndex: number,
) {
  return api(`/conversations/${conversationId}/review-items`, {
    method: "POST",
    body: JSON.stringify({
      message_id: messageId,
      correction_index: correctionIndex,
      save_all: false,
    }),
  });
}

export function listReviewItems(includeResolved = false) {
  return api<{ items: ReviewItem[] }>(
    `/review-items?include_resolved=${includeResolved}`,
  );
}

export function resolveReviewItem(id: number, isResolved: boolean) {
  return api<ReviewItem>(`/review-items/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ is_resolved: isResolved }),
  });
}

export function deleteReviewItem(id: number) {
  return api(`/review-items/${id}`, { method: "DELETE" });
}

type StreamHandlers = {
  onDelta: (text: string) => void;
};

type TurnResult = {
  turn: {
    user_message: ChatMessage;
    assistant_message: ChatMessage;
  };
};

export async function streamConversationTurn(
  conversationId: number,
  text: string,
  handlers: StreamHandlers,
): Promise<TurnResult> {
  const resp = await fetch(
    `/api/v1/conversations/${conversationId}/messages/stream`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getToken() ?? ""}`,
      },
      body: JSON.stringify({ text }),
    },
  );
  if (!resp.ok || !resp.body) {
    let detail = "对话服务暂不可用";
    try {
      detail = (await resp.json()).detail || detail;
    } catch {}
    throw new Error(detail);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let final: TurnResult | null = null;
  let errorDetail = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const lines = chunk.split("\n");
      let event = "message";
      const dataLines: string[] = [];
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (!dataLines.length) continue;
      const data = JSON.parse(dataLines.join("\n"));
      if (event === "delta") handlers.onDelta(data.text);
      if (event === "final") final = data as TurnResult;
      if (event === "error") errorDetail = data.detail || "保存失败";
    }
  }

  if (errorDetail) throw new Error(errorDetail);
  if (!final) throw new Error("对话返回不完整，请重试");
  return final;
}
