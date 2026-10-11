"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { playSentence, playWord } from "@/lib/audio";

type Word = {
  id: number;
  headword: string;
  phonetic: string | null;
  pos: string | null;
  definition_en: string | null;
  translation: string | null;
  unit: string | null;
  examples: string[];
  favorite: boolean;
};

const GRADES = [
  { grade: 0, label: "不认识", cls: "bg-red-500" },
  { grade: 1, label: "模糊", cls: "bg-orange-500" },
  { grade: 2, label: "认识", cls: "bg-emerald-500" },
  { grade: 3, label: "很熟", cls: "bg-blue-500" },
];

export default function LearnPage() {
  const router = useRouter();
  const [words, setWords] = useState<Word[]>([]);
  const [idx, setIdx] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [total, setTotal] = useState(0);
  const [done, setDone] = useState(0);
  const [loading, setLoading] = useState(true);
  const [finished, setFinished] = useState(false);
  const [fav, setFav] = useState(false);

  useEffect(() => {
    api<{ due: Word[]; new: Word[] }>("/learn/queue")
      .then((q) => {
        const list = [...q.due, ...q.new];
        setWords(list);
        setTotal(list.length);
        setFav(list[0]?.favorite ?? false);
      })
      .finally(() => setLoading(false));
  }, []);

  const word = words[idx];

  async function grade(g: number) {
    if (!word) return;
    await api("/learn/review", {
      method: "POST",
      body: JSON.stringify({ word_id: word.id, grade: g }),
    });
    setDone((d) => d + 1);
    if (idx + 1 >= words.length) {
      setFinished(true);
    } else {
      setIdx(idx + 1);
      setFav(words[idx + 1]?.favorite ?? false);
      setFlipped(false);
    }
  }

  async function toggleFav() {
    if (!word) return;
    const next = !fav;
    setFav(next);
    await api(`/words/${word.id}/favorite`, {
      method: "POST",
      body: JSON.stringify({ favorite: next }),
    });
  }

  if (loading) {
    return <div className="p-10 text-center text-slate-400">加载中…</div>;
  }

  if (finished || !word) {
    return (
      <div className="flex min-h-[80vh] flex-col items-center justify-center px-8 text-center">
        <div className="text-6xl">🎉</div>
        <h2 className="mt-4 text-xl font-bold">今日学习完成</h2>
        <p className="mt-2 text-slate-500">
          本轮共学习 {total} 个单词，去听写巩固一下？
        </p>
        <div className="mt-6 flex w-full gap-3">
          <button
            onClick={() => router.push("/dictation")}
            className="flex-1 rounded-xl bg-brand py-3 font-medium text-white"
          >
            去听写
          </button>
          <button
            onClick={() => router.push("/")}
            className="flex-1 rounded-xl border border-slate-300 py-3 font-medium"
          >
            回首页
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col px-5 pt-6">
      <div className="flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-brand transition-all"
            style={{ width: `${(done / total) * 100}%` }}
          />
        </div>
        <span className="text-xs text-slate-400">
          {done + 1}/{total}
        </span>
      </div>

      <div
        className="mt-6 flex-1 cursor-pointer select-none rounded-3xl border border-slate-200 bg-white p-7 shadow-sm"
        onClick={() => setFlipped(true)}
      >
        <div className="flex items-start justify-between">
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-500">
            {word.unit ?? "考纲词汇"}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              toggleFav();
            }}
            className="text-2xl"
          >
            {fav ? "⭐" : "☆"}
          </button>
        </div>

        <div className="mt-8 text-center">
          <h1 className="text-4xl font-bold tracking-tight">{word.headword}</h1>
          <div className="mt-3 flex items-center justify-center gap-3 text-slate-500">
            {word.phonetic && (
              <span className="text-sm">{word.phonetic}</span>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                playWord(word.id, "us").catch(() => {});
              }}
              className="rounded-full bg-brand/10 px-3 py-1 text-sm text-brand"
            >
              🔊 美音
            </button>
          </div>
        </div>

        {!flipped ? (
          <p className="mt-16 text-center text-sm text-slate-400">
            点击卡片显示释义
          </p>
        ) : (
          <div className="mt-8">
            {word.pos && (
              <p className="text-sm font-medium text-brand">{word.pos}</p>
            )}
            {word.translation && (
              <p className="mt-1 text-lg leading-relaxed text-slate-800">
                {word.translation}
              </p>
            )}
            {word.definition_en && (
              <p className="mt-2 text-sm leading-relaxed text-slate-400">
                {word.definition_en.split("\n").slice(0, 2).join("；")}
              </p>
            )}
            {word.examples.length > 0 && (
              <div className="mt-5 space-y-3 border-t border-slate-100 pt-4">
                {word.examples.slice(0, 2).map((ex, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        const en = ex.split(/[（(]/)[0].trim();
                        playSentence(en).catch(() => {});
                      }}
                      className="mt-0.5 shrink-0 text-brand"
                    >
                      🔊
                    </button>
                    <p className="leading-relaxed text-slate-600">{ex}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-4 gap-2 py-6">
        {GRADES.map((g) => (
          <button
            key={g.grade}
            onClick={() => grade(g.grade)}
            className={`rounded-xl ${g.cls} py-3 text-sm font-medium text-white`}
          >
            {g.label}
          </button>
        ))}
      </div>
    </div>
  );
}
