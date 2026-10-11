import { api, getToken } from "./api";
import { playBlob } from "./audio";

export type DictationSource = "auto" | "review" | "patterns" | "lines" | "words";

export type DictationItem = {
  item_id: string;
  source_type: "pattern" | "line" | "word_example" | "review";
  source_id: number;
  sentence_index: number;
  zh_hint: string;
  source_title: string;
  word_count: number;
  streak?: number | null;
};

export type CheckToken = {
  target: string | null;
  answer: string | null;
  status: "ok" | "wrong" | "missing" | "extra";
  kind?: string;
};

export type CheckError = {
  kind: string;
  expected: string | null;
  got: string | null;
};

export type CheckResult = {
  correct: boolean;
  score: number;
  your_answer: string;
  target: string;
  tokens: CheckToken[];
  errors: CheckError[];
  kind_counts: Record<string, number>;
  zh_hint: string;
  source_title: string;
  review_action: "none" | "added" | "streak" | "mastered";
  review_streak: number;
};

export const ERROR_KIND_ZH: Record<string, string> = {
  spelling: "拼写",
  form: "时态/形态",
  missing: "漏词",
  extra: "多词",
  word_order: "词序",
};

export async function fetchQueue(source: DictationSource, limit = 10) {
  return api<{ items: DictationItem[] }>(
    `/dictation/sentence-queue?source=${source}&limit=${limit}`,
  );
}

export async function checkSentence(
  item: DictationItem,
  answer: string,
  hintCount: number,
) {
  return api<CheckResult>("/dictation/sentence-check", {
    method: "POST",
    body: JSON.stringify({
      source_type: item.source_type,
      source_id: item.source_id,
      sentence_index: item.sentence_index,
      answer,
      hint_count: hintCount,
    }),
  });
}

export async function playDictation(
  item: Pick<DictationItem, "source_type" | "source_id" | "sentence_index">,
  speed: "normal" | "slow" = "normal",
) {
  const qs = new URLSearchParams({
    source_type: item.source_type,
    source_id: String(item.source_id),
    sentence_index: String(item.sentence_index),
    speed,
  });
  const resp = await fetch(`/api/v1/dictation/audio?${qs}`, {
    headers: { Authorization: `Bearer ${getToken() ?? ""}` },
  });
  if (!resp.ok) throw new Error("音频加载失败");
  return playBlob(await resp.blob());
}
