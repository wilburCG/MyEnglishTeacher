"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { playWord } from "@/lib/audio";

type Word = {
  id: number;
  headword: string;
  phonetic: string | null;
  translation: string | null;
  examples: string[];
};

type Result = {
  correct: boolean;
  your_answer: string;
  target: string;
  distance: number;
  similarity: number;
};

export default function DictationPage() {
  const router = useRouter();
  const [words, setWords] = useState<Word[]>([]);
  const [idx, setIdx] = useState(0);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [plays, setPlays] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);
  const [finished, setFinished] = useState(false);
  const [loading, setLoading] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);

  const word = words[idx];

  useEffect(() => {
    api<{ words: Word[] }>("/learn/dictation-queue")
      .then((q) => setWords(q.words))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (word && !result) {
      playWord(word.id).catch(() => {});
      setPlays(1);
      inputRef.current?.focus();
    }
  }, [word, result]);

  async function replay() {
    if (!word) return;
    await playWord(word.id).catch(() => {});
    setPlays((p) => p + 1);
  }

  async function submit() {
    if (!word || !answer.trim() || result) return;
    const r = await api<Result>("/learn/dictation", {
      method: "POST",
      body: JSON.stringify({ word_id: word.id, answer: answer }),
    });
    setResult(r);
    if (r.correct) setCorrectCount((c) => c + 1);
  }

  function next() {
    if (idx + 1 >= words.length) {
      setFinished(true);
      return;
    }
    setIdx(idx + 1);
    setAnswer("");
    setResult(null);
    setPlays(0);
  }

  if (loading) {
    return <div className="p-10 text-center text-slate-400">加载中…</div>;
  }

  if (finished) {
    return (
      <div className="flex min-h-[80vh] flex-col items-center justify-center px-8 text-center">
        <div className="text-6xl">{correctCount === words.length ? "🏆" : "✅"}</div>
        <h2 className="mt-4 text-xl font-bold">听写完成</h2>
        <p className="mt-2 text-slate-500">
          正确 {correctCount} / {words.length} 个
        </p>
        <button
          onClick={() => router.push("/")}
          className="mt-6 w-full rounded-xl bg-brand py-3 font-medium text-white"
        >
          回首页
        </button>
      </div>
    );
  }

  if (!word) {
    return <div className="p-10 text-center text-slate-400">暂无可听写的单词</div>;
  }

  return (
    <div className="flex min-h-screen flex-col px-5 pt-8">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">单词听写</h1>
        <span className="text-sm text-slate-400">
          {idx + 1}/{words.length} · 已听 {plays} 次
        </span>
      </div>

      <div className="mt-6 rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <button
          onClick={replay}
          className="mx-auto flex h-24 w-24 items-center justify-center rounded-full bg-brand/10 text-4xl text-brand active:scale-95"
        >
          🔊
        </button>
        <p className="mt-4 text-sm text-slate-400">
          听发音，拼写单词（点喇叭重听）
        </p>

        <input
          ref={inputRef}
          className="mt-6 w-full rounded-xl border-2 border-slate-200 px-4 py-3.5 text-center text-2xl tracking-wider outline-none focus:border-brand"
          placeholder="输入拼写"
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          value={answer}
          disabled={!!result}
          onChange={(e) => setAnswer(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />

        {!result ? (
          <button
            onClick={submit}
            disabled={!answer.trim()}
            className="mt-4 w-full rounded-xl bg-brand py-3 font-medium text-white disabled:bg-slate-300"
          >
            提交
          </button>
        ) : (
          <div className="mt-5 text-left">
            <div
              className={`rounded-xl p-4 ${
                result.correct ? "bg-emerald-50" : "bg-red-50"
              }`}
            >
              <p
                className={`font-semibold ${
                  result.correct ? "text-emerald-700" : "text-red-700"
                }`}
              >
                {result.correct ? "✓ 正确" : "✗ 再记一下"}
              </p>
              <p className="mt-1 text-2xl font-bold">{result.target}</p>
              {word.phonetic && (
                <p className="mt-1 text-sm text-slate-500">{word.phonetic}</p>
              )}
              {word.translation && (
                <p className="mt-1 text-slate-600">{word.translation}</p>
              )}
              {!result.correct && (
                <p className="mt-2 text-sm text-red-600">
                  你的答案：{result.your_answer || "（空）"} · 相似度{" "}
                  {Math.round(result.similarity * 100)}%
                </p>
              )}
            </div>
            <button
              onClick={next}
              className="mt-4 w-full rounded-xl bg-brand py-3 font-medium text-white"
            >
              {idx + 1 >= words.length ? "查看结果" : "下一个"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
