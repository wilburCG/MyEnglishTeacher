"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { playSentence } from "@/lib/audio";
import {
  ChatMessage,
  Conversation,
  ConversationReport,
  Correction,
  finishConversation,
  getConversation,
  KIND_COLOR,
  KIND_LABEL,
  saveAllReviewItems,
  saveOneReviewItem,
  startConversation,
  streamConversationTurn,
} from "@/lib/conversation";

export default function SpeakChatPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const conversationId = Number(params.id);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [pendingText, setPendingText] = useState("");
  const [err, setErr] = useState("");
  const [report, setReport] = useState<ConversationReport | null>(null);
  const [finishing, setFinishing] = useState(false);
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set());
  const [savedAll, setSavedAll] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    const data = await getConversation(conversationId);
    setConversation(data.conversation);
    setMessages(data.messages);
    if (data.conversation.report) setReport(data.conversation.report);
    setLoading(false);
  }, [conversationId]);

  useEffect(() => {
    load().catch((e) => {
      setErr(e.message);
      setLoading(false);
    });
  }, [load]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText, pendingText]);

  function markSaved(messageId: number, index: number) {
    setSavedKeys((set) => new Set(set).add(`${messageId}:${index}`));
  }

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    setSending(true);
    setErr("");
    setInput("");
    setPendingText(text);
    setStreamingText("");
    try {
      const result = await streamConversationTurn(conversationId, text, {
        onDelta: (delta) => setStreamingText((v) => v + delta),
      });
      setPendingText("");
      setStreamingText("");
      setMessages((list) => [
        ...list,
        result.turn.user_message,
        result.turn.assistant_message,
      ]);
      setConversation((c) =>
        c ? { ...c, turn_count: c.turn_count + 1 } : c,
      );
    } catch (e: any) {
      setErr(e.message || "发送失败");
      setInput(text);
      setPendingText("");
      setStreamingText("");
    } finally {
      setSending(false);
    }
  }

  async function finish() {
    if (!conversation || finishing) return;
    setFinishing(true);
    setErr("");
    try {
      const r = await finishConversation(conversation.id);
      setReport(r.report);
      setConversation((c) => (c ? { ...c, status: "finished", report: r.report } : c));
    } catch (e: any) {
      setErr(e.message || "生成报告失败");
    } finally {
      setFinishing(false);
    }
  }

  async function saveAll() {
    if (!conversation) return;
    const r = await saveAllReviewItems(conversation.id);
    setSavedAll(true);
    setErr(r.count ? "" : "没有需要保存的错误");
  }

  async function practiceAgain() {
    if (!conversation) return;
    const c = await startConversation(conversation.scenario_id);
    router.push(`/speak/${c.id}`);
  }

  if (loading) {
    return <div className="px-5 pt-16 text-center text-sm text-slate-400">加载中…</div>;
  }

  const ended = conversation?.status === "finished";

  return (
    <div className="flex h-[calc(100dvh-56px)] flex-col">
      <header className="border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex items-center gap-3">
          <Link href="/speak" className="text-slate-400">
            ←
          </Link>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-slate-800">
              {conversation?.title_zh}
            </p>
            <p className="truncate text-xs text-slate-400">
              {conversation?.theme} · 第 {conversation?.turn_count} 轮
            </p>
          </div>
          {!ended && (
            <button
              onClick={finish}
              disabled={finishing || (conversation?.turn_count ?? 0) === 0}
              className="rounded-full border border-brand px-3 py-1.5 text-xs font-medium text-brand disabled:opacity-40"
            >
              {finishing ? "总结中…" : "结束并出报告"}
            </button>
          )}
        </div>
      </header>

      <main className="flex-1 space-y-4 overflow-y-auto bg-slate-50 px-4 py-4">
        <div className="rounded-2xl border border-brand/15 bg-brand/5 p-3 text-xs leading-5 text-slate-600">
          <p className="font-medium text-brand">任务</p>
          <p>{conversation?.scenario?.goal}</p>
          {conversation?.scenario?.recommended_words?.length ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {conversation.scenario.recommended_words.map((w) => (
                <span key={w} className="rounded-full bg-white px-2 py-0.5 text-brand">
                  {w}
                </span>
              ))}
            </div>
          ) : null}
        </div>

        {messages.map((m, idx) => (
          <MessageBubble
            key={m.id ?? idx}
            conversationId={conversationId}
            message={m}
            saved={savedKeys}
            onSaved={markSaved}
          />
        ))}

        {pendingText && (
          <div className="flex justify-end">
            <div className="max-w-[82%] rounded-2xl rounded-br-md bg-white px-3.5 py-2.5 text-sm shadow-sm">
              {pendingText}
            </div>
          </div>
        )}
        {streamingText && (
          <div className="flex justify-start">
            <div className="max-w-[86%] rounded-2xl rounded-bl-md bg-brand px-3.5 py-2.5 text-sm leading-6 text-white shadow-sm">
              {streamingText}
              <span className="ml-0.5 animate-pulse">▍</span>
            </div>
          </div>
        )}
        {sending && !streamingText && (
          <p className="text-center text-xs text-slate-400">老师正在思考，通常需要 5–15 秒…</p>
        )}
        <div ref={bottomRef} />
      </main>

      {report && (
        <ReportPanel
          report={report}
          savedAll={savedAll}
          onSaveAll={saveAll}
          onPracticeAgain={practiceAgain}
          onClose={() => setReport(null)}
        />
      )}

      {err && <p className="bg-red-50 px-4 py-2 text-center text-xs text-red-500">{err}</p>}

      <footer className="border-t border-slate-200 bg-white p-3 pb-5">
        {ended ? (
          <div className="flex gap-2">
            <button
              onClick={() => conversation.report && setReport(conversation.report)}
              className="flex-1 rounded-xl border border-slate-200 py-3 text-sm text-slate-600"
            >
              查看报告
            </button>
            <button
              onClick={practiceAgain}
              className="flex-1 rounded-xl bg-brand py-3 text-sm font-medium text-white"
            >
              再练一次
            </button>
          </div>
        ) : (
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value.slice(0, 500))}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              rows={1}
              placeholder="用英语回复老师…"
              className="max-h-28 flex-1 resize-none rounded-2xl border border-slate-200 px-3.5 py-2.5 text-sm outline-none focus:border-brand"
            />
            <button
              onClick={send}
              disabled={sending || !input.trim()}
              className="rounded-2xl bg-brand px-5 py-2.5 text-sm font-medium text-white disabled:opacity-40"
            >
              发送
            </button>
          </div>
        )}
      </footer>
    </div>
  );
}

function MessageBubble({
  conversationId,
  message,
  saved,
  onSaved,
}: {
  conversationId: number;
  message: ChatMessage;
  saved: Set<string>;
  onSaved: (messageId: number, index: number) => void;
}) {
  const isUser = message.role === "user";
  const audioText = shortForTts(message.content);

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[88%] ${isUser ? "w-[86%]" : "w-[90%]"}`}>
        <div
          className={`rounded-2xl px-3.5 py-2.5 text-sm leading-6 shadow-sm ${
            isUser
              ? "rounded-br-md bg-white text-slate-800"
              : "rounded-bl-md bg-brand text-white"
          }`}
        >
          <div className="flex items-start gap-2">
            <p className="flex-1">{message.content}</p>
            {audioText && (
              <button
                onClick={() => playSentence(audioText).catch(() => {})}
                className={isUser ? "text-brand" : "text-white/85"}
                aria-label="播放发音"
              >
                🔊
              </button>
            )}
          </div>
        </div>

        {isUser && message.corrections && message.corrections.length > 0 && (
          <div className="mt-2 space-y-2">
            {message.corrections.map((c, i) => (
              <CorrectionCard
                key={`${message.id}-${i}`}
                conversationId={conversationId}
                messageId={message.id}
                index={i}
                correction={c}
                isSaved={message.id ? saved.has(`${message.id}:${i}`) : false}
                onSaved={onSaved}
              />
            ))}
          </div>
        )}

        {isUser && message.better_version && (
          <details className="mt-2 rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
            <summary className="cursor-pointer font-medium">更地道的说法</summary>
            <p className="mt-1 leading-5">{message.better_version}</p>
          </details>
        )}

        {!isUser && message.hint_zh && (
          <p className="mt-1 pl-1 text-xs text-slate-400">💡 {message.hint_zh}</p>
        )}
        {isUser && message.model_validated === false && (
          <p className="mt-1 pr-1 text-right text-[11px] text-slate-400">
            本次纠错服务暂不可用，未展示批改
          </p>
        )}
      </div>
    </div>
  );
}

function CorrectionCard({
  conversationId,
  messageId,
  index,
  correction,
  isSaved,
  onSaved,
}: {
  conversationId: number;
  messageId?: number;
  index: number;
  correction: Correction;
  isSaved: boolean;
  onSaved: (messageId: number, index: number) => void;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <div className="rounded-xl border border-red-100 bg-red-50/70 p-3 text-xs text-slate-700">
      <div className="flex items-center justify-between gap-2">
        <span
          className={`rounded-full border px-2 py-0.5 text-[11px] ${
            KIND_COLOR[correction.kind] || KIND_COLOR.grammar
          }`}
        >
          {KIND_LABEL[correction.kind] || "语法"}
        </span>
        {messageId !== undefined && (
          <button
            disabled={isSaved || busy}
            onClick={async () => {
              setBusy(true);
              try {
                await saveOneReviewItem(conversationId, messageId, index);
                onSaved(messageId, index);
              } finally {
                setBusy(false);
              }
            }}
            className="text-[11px] font-medium text-brand disabled:text-slate-400"
          >
            {isSaved ? "已加入复习本" : "加入复习本"}
          </button>
        )}
      </div>
      <p className="mt-2 leading-5">
        <span className="mr-2 rounded bg-red-100 px-1.5 py-0.5 text-red-700 line-through">
          {correction.original}
        </span>
        →
        <span className="ml-2 rounded bg-emerald-100 px-1.5 py-0.5 text-emerald-700">
          {correction.corrected}
        </span>
      </p>
      <p className="mt-1.5 leading-5 text-slate-600">{correction.explanation_zh}</p>
    </div>
  );
}

function ReportPanel({
  report,
  savedAll,
  onSaveAll,
  onPracticeAgain,
  onClose,
}: {
  report: ConversationReport;
  savedAll: boolean;
  onSaveAll: () => void;
  onPracticeAgain: () => void;
  onClose: () => void;
}) {
  const maxKind = Math.max(1, ...Object.values(report.kind_counts || {}));
  return (
    <div className="fixed inset-0 z-30 flex items-end justify-center bg-black/30" onClick={onClose}>
      <div
        className="max-h-[88vh] w-full max-w-md overflow-y-auto rounded-t-3xl bg-white p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-slate-200" />
        <h2 className="text-lg font-bold">对话报告</h2>
        <p className="mt-1 text-sm text-slate-500">
          {report.total_sentences} 句 · {report.error_sentences} 句有待改进
        </p>

        <div className="mt-4 rounded-2xl bg-brand/5 p-4">
          <p className="text-sm font-medium text-brand">{report.teacher.encouragement_en}</p>
          <p className="mt-1 text-sm text-slate-700">{report.teacher.encouragement_zh}</p>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2 text-center">
          <div className="rounded-2xl bg-slate-50 p-3">
            <p className="text-xl font-bold">{report.total_sentences}</p>
            <p className="text-xs text-slate-400">总句数</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-3">
            <p className="text-xl font-bold">{report.correction_count}</p>
            <p className="text-xs text-slate-400">纠错点</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-3">
            <p className="text-xl font-bold">{report.accuracy ?? "-"}%</p>
            <p className="text-xs text-slate-400">正确率</p>
          </div>
        </div>

        {Object.keys(report.kind_counts || {}).length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-semibold">薄弱点分布</h3>
            <div className="mt-2 space-y-2">
              {Object.entries(report.kind_counts).map(([kind, count]) => (
                <div key={kind} className="flex items-center gap-2 text-xs">
                  <span className="w-16 text-slate-500">{KIND_LABEL[kind] || kind}</span>
                  <div className="h-2 flex-1 rounded-full bg-slate-100">
                    <div
                      className="h-2 rounded-full bg-brand"
                      style={{ width: `${(count / maxKind) * 100}%` }}
                    />
                  </div>
                  <span className="w-5 text-right">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {report.corrections.length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-semibold">典型错句</h3>
            <div className="mt-2 space-y-2">
              {report.corrections.slice(0, 6).map((c, i) => (
                <div key={i} className="rounded-xl bg-slate-50 p-3 text-xs leading-5">
                  <p>
                    <span className="text-red-500 line-through">{c.original}</span>
                    {" → "}
                    <span className="text-emerald-600">{c.corrected}</span>
                  </p>
                  <p className="mt-1 text-slate-500">{c.explanation_zh}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mt-4 rounded-2xl border border-amber-100 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-medium">下一步建议</p>
          <ul className="mt-1 list-inside list-disc space-y-1 text-xs leading-5">
            {report.teacher.next_tips.map((tip, i) => (
              <li key={i}>{tip}</li>
            ))}
          </ul>
        </div>

        <div className="mt-5 flex gap-2 pb-4">
          <button
            onClick={onSaveAll}
            disabled={savedAll || report.correction_count === 0}
            className="flex-1 rounded-xl border border-brand py-3 text-sm font-medium text-brand disabled:border-slate-200 disabled:text-slate-400"
          >
            {savedAll ? "已保存到复习本" : "错误一键入复习本"}
          </button>
          <button
            onClick={onPracticeAgain}
            className="flex-1 rounded-xl bg-brand py-3 text-sm font-medium text-white"
          >
            再练一次
          </button>
        </div>
      </div>
    </div>
  );
}

function shortForTts(text: string) {
  if (text.length <= 180) return text;
  const first = text.split(/(?<=[.!?])\s+/)[0];
  return first.slice(0, 180);
}
