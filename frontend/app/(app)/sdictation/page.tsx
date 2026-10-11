"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  checkSentence,
  CheckResult,
  DictationItem,
  DictationSource,
  ERROR_KIND_ZH,
  fetchQueue,
  playDictation,
} from "@/lib/dictation";
import { playSentence } from "@/lib/audio";

const TABS: { key: DictationSource; label: string }[] = [
  { key: "auto", label: "智能复习" },
  { key: "review", label: "错句重听" },
  { key: "patterns", label: "句型例句" },
  { key: "lines", label: "台词" },
  { key: "words", label: "单词例句" },
];

export default function SentenceDictationPage() {
  const [source, setSource] = useState<DictationSource>(
    () => {
      if (typeof window === "undefined") return "auto";
      const q = new URLSearchParams(window.location.search).get("source");
      return (TABS.some((t) => t.key === q) ? q : "auto") as DictationSource;
    }
  );
  const [queue, setQueue] = useState<DictationItem[]>([]);
  const [idx, setIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<CheckResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [hints, setHints] = useState(0);
  const [playing, setPlaying] = useState<"" | "normal" | "slow">("");
  const [showZh, setShowZh] = useState(false);
  const [err, setErr] = useState("");
  const [done, setDone] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);
  const audioPlayed = useRef(false);

  const load = useCallback(async (s: DictationSource) => {
    setLoading(true);
    setErr("");
    try {
      const r = await fetchQueue(s);
      setQueue(r.items);
      setIdx(0);
    } catch (e: any) {
      setErr(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(source);
  }, [source, load]);

  const item = queue[idx];

  const resetCard = useCallback(() => {
    setAnswer("");
    setResult(null);
    setHints(0);
    setShowZh(false);
    audioPlayed.current = false;
  }, []);

  useEffect(() => {
    resetCard();
  }, [idx, source, resetCard]);

  async function play(speed: "normal" | "slow") {
    if (!item) return;
    setPlaying(speed);
    try {
      await playDictation(item, speed);
      if (audioPlayed.current && speed === "normal") {
        setHints((h) => h + 1);
      }
      if (speed === "slow") {
        setHints((h) => h + 1);
      }
      audioPlayed.current = true;
    } catch {
      setErr("发音加载失败，可重试");
    } finally {
      setPlaying("");
    }
  }

  async function submit() {
    if (!item || !answer.trim() || submitting) return;
    setSubmitting(true);
    setErr("");
    try {
      const r = await checkSentence(item, answer, hints);
      setResult(r);
      setDone((n) => n + 1);
      if (r.correct) setCorrectCount((n) => n + 1);
    } catch (e: any) {
      setErr(e.message || "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  function next() {
    if (idx + 1 < queue.length) {
      setIdx((i) => i + 1);
    } else {
      setIdx(queue.length); // 结束态
    }
  }

  return (
    <div className="px-5 pt-8 pb-10">
      <Link href="/dictation" className="text-sm text-slate-400">
        ← 单词听写
      </Link>
      <h1 className="mt-3 text-xl font-bold">句子听写</h1>
      <p className="mt-1 text-sm text-slate-500">
        听句子写下来；错句自动进复习本，连续两次正确即掌握。
      </p>

      <div className="mt-4 flex gap-1.5 overflow-x-auto pb-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setSource(t.key)}
            className={`shrink-0 rounded-full px-3.5 py-1.5 text-sm ${
              source === t.key
                ? "bg-brand font-medium text-white"
                : "bg-slate-100 text-slate-500"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="mt-16 text-center text-sm text-slate-400">加载中…</p>
      ) : queue.length === 0 ? (
        <div className="mt-12 rounded-3xl border border-dashed border-slate-200 bg-white p-10 text-center">
          <p className="text-3xl">🎉</p>
          <p className="mt-2 text-sm text-slate-500">
            {source === "review" ? "错句都掌握了，太棒了" : "当前级别暂时没有材料"}
          </p>
          {source === "review" && (
            <Link
              href="/sdictation?x=1"
              onClick={() => setSource("patterns")}
              className="mt-4 inline-block rounded-xl bg-brand px-5 py-2.5 text-sm font-medium text-white"
            >
              去练句型例句
            </Link>
          )}
        </div>
      ) : idx >= queue.length ? (
        <div className="mt-12 rounded-3xl border border-slate-200 bg-white p-8 text-center">
          <p className="text-4xl">✅</p>
          <p className="mt-3 text-lg font-semibold">本组完成</p>
          <p className="mt-1 text-sm text-slate-500">
            {done} 句 · 首次正确 {correctCount} 句
          </p>
          <button
            onClick={() => load(source)}
            className="mt-5 rounded-xl bg-brand px-6 py-2.5 text-sm font-medium text-white"
          >
            再来一组
          </button>
        </div>
      ) : (
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>{idx + 1} / {queue.length} · {item.source_title}</span>
            <span>{item.word_count} 词</span>
          </div>
          {item.source_type === "review" && (
            <p className="mt-1 text-xs font-medium text-amber-600">
              错句重听 · 已连续正确 {item.streak ?? 0} 次，再对 {Math.max(0, 2 - (item.streak ?? 0))} 次掌握
            </p>
          )}

          <div className="mt-3 rounded-3xl border border-slate-200 bg-white p-6">
            <div className="flex items-center justify-center gap-4">
              <button
                onClick={() => play("normal")}
                disabled={playing !== ""}
                className="flex h-16 w-16 items-center justify-center rounded-full bg-brand text-2xl text-white shadow-lg shadow-brand/25 disabled:opacity-50"
              >
                {playing === "normal" ? "…" : "🔊"}
              </button>
              <button
                onClick={() => play("slow")}
                disabled={playing !== ""}
                className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-lg disabled:opacity-50"
                title="慢速播放"
              >
                🐢
              </button>
            </div>
            <p className="mt-2 text-center text-xs text-slate-400">
              点喇叭播放{hints > 0 ? ` · 已用提示 ${hints} 次` : ""}
            </p>

            <button
              onClick={() => {
                setShowZh(true);
                setHints((h) => h + 1);
              }}
              className="mx-auto mt-3 block text-xs text-brand"
            >
              {showZh ? `中文提示：${item.zh_hint || "（无）"}` : "看中文提示"}
            </button>

            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value.slice(0, 600))}
              disabled={!!result}
              rows={3}
              placeholder="把听到的句子写下来…"
              className="mt-4 w-full resize-none rounded-2xl border border-slate-200 p-3.5 text-base outline-none focus:border-brand disabled:bg-slate-50"
            />

            {!result ? (
              <button
                onClick={submit}
                disabled={!answer.trim() || submitting}
                className="mt-3 w-full rounded-xl bg-brand py-3 text-sm font-medium text-white disabled:opacity-40"
              >
                {submitting ? "判题中…" : "提交"}
              </button>
            ) : (
              <ResultPanel result={result} onNext={next} last={idx + 1 >= queue.length} />
            )}
            {err && <p className="mt-2 text-center text-xs text-red-500">{err}</p>}
          </div>
        </div>
      )}
    </div>
  );
}

function ResultPanel({
  result,
  onNext,
  last,
}: {
  result: CheckResult;
  onNext: () => void;
  last: boolean;
}) {
  const banner = result.correct
    ? "bg-emerald-50 text-emerald-700"
    : result.score >= 60
      ? "bg-amber-50 text-amber-700"
      : "bg-red-50 text-red-600";

  const reviewNote: Record<string, string> = {
    added: "📒 已加入错句复习本",
    streak: `不错！再连续对 1 次就掌握`,
    mastered: "🎉 已掌握，错句出复习本",
    none: "",
  };

  return (
    <div className="mt-4">
      <div className={`rounded-2xl p-3 text-center text-sm font-medium ${banner}`}>
        {result.correct
          ? "完全正确！"
          : `得分 ${result.score} 分`}
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5 leading-8">
        {result.tokens.map((t, i) => {
          if (t.status === "ok") {
            return <span key={i} className="text-base text-emerald-700">{t.target} </span>;
          }
          if (t.status === "missing") {
            return (
              <span key={i} className="rounded bg-red-50 px-1.5 text-base text-red-400 line-through">
                {t.target}
              </span>
            );
          }
          if (t.status === "extra") {
            return (
              <span key={i} className="rounded bg-slate-100 px-1.5 text-base text-slate-400 line-through">
                {t.answer}
              </span>
            );
          }
          return (
            <span key={i} className="rounded bg-red-100 px-1.5 text-base text-red-600" title={ERROR_KIND_ZH[t.kind || ""] || t.kind}>
              {t.answer}
              <span className="text-red-400">→{t.target}</span>
            </span>
          );
        })}
      </div>

      {result.errors.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {result.errors.map((e, i) => (
            <p key={i} className="rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600">
              <span className="mr-1.5 rounded bg-slate-200 px-1.5 py-0.5 text-slate-600">
                {ERROR_KIND_ZH[e.kind] || e.kind}
              </span>
              {e.got ? <span className="text-red-500 line-through">{e.got}</span> : null}
              {e.got ? " → " : null}
              <span className="text-emerald-700">{e.expected ?? "（漏写）"}</span>
            </p>
          ))}
        </div>
      )}

      <div className="mt-3 rounded-2xl bg-brand/5 p-3">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium text-slate-800">{result.target}</p>
          <button
            onClick={() => playSentence(result.target).catch(() => {})}
            className="shrink-0 text-brand"
          >
            🔊
          </button>
        </div>
        {result.zh_hint && (
          <p className="mt-1 text-xs text-slate-500">{result.zh_hint}</p>
        )}
      </div>

      {reviewNote[result.review_action] && (
        <p className="mt-2 text-center text-xs font-medium text-amber-600">
          {reviewNote[result.review_action]}
        </p>
      )}

      <button
        onClick={onNext}
        className="mt-3 w-full rounded-xl bg-brand py-3 text-sm font-medium text-white"
      >
        {last ? "完成本组" : "下一句 →"}
      </button>
    </div>
  );
}
