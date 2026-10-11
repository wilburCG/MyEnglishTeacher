"use client";

import { useEffect, useState } from "react";
import { playSentence } from "@/lib/audio";
import { listPatterns, Pattern, setContentFavorite } from "@/lib/content";

export default function PatternsPage() {
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [loading, setLoading] = useState(true);
  const [allLevels, setAllLevels] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const [favs, setFavs] = useState<Record<number, boolean>>({});

  useEffect(() => {
    setLoading(true);
    listPatterns({ includeAll: allLevels })
      .then((list) => {
        setPatterns(list);
        setFavs(Object.fromEntries(list.map((p) => [p.id, p.favorite])));
      })
      .finally(() => setLoading(false));
  }, [allLevels]);

  async function toggleFav(p: Pattern) {
    const next = !favs[p.id];
    setFavs((m) => ({ ...m, [p.id]: next }));
    await setContentFavorite("pattern", p.id, next).catch(() => {});
  }

  return (
    <div className="px-5 pt-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">典型句型</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            {allLevels ? "全部级别" : `初一 · ${patterns.length} 个句型`}
          </p>
        </div>
        <button
          onClick={() => setAllLevels((v) => !v)}
          className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600"
        >
          {allLevels ? "只看本级别" : "全部级别"}
        </button>
      </header>

      {loading ? (
        <p className="py-16 text-center text-slate-400">加载中…</p>
      ) : patterns.length === 0 ? (
        <p className="py-16 text-center text-slate-400">
          该级别句型还在准备中
        </p>
      ) : (
        <div className="mt-5 space-y-3 pb-6">
          {patterns.map((p) => {
            const open = openId === p.id;
            return (
              <div
                key={p.id}
                className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
              >
                <div
                  className="flex cursor-pointer items-start gap-3"
                  onClick={() => setOpenId(open ? null : p.id)}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="rounded bg-brand/10 px-1.5 py-0.5 text-[10px] text-brand">
                        {p.theme}
                      </span>
                      {p.unit && (
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">
                          {p.unit}
                        </span>
                      )}
                    </div>
                    <p className="mt-2 text-lg font-semibold text-slate-800">
                      {p.template}
                    </p>
                    <p className="mt-0.5 text-sm text-slate-500">{p.func_zh}</p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleFav(p);
                    }}
                    className="text-xl"
                  >
                    {favs[p.id] ? "⭐" : "☆"}
                  </button>
                </div>

                {open && (
                  <div className="mt-3 border-t border-slate-100 pt-3">
                    {p.grammar_point && (
                      <p className="text-xs font-medium text-emerald-600">
                        语法点：{p.grammar_point}
                      </p>
                    )}
                    {p.explanation_zh && (
                      <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
                        {p.explanation_zh}
                      </p>
                    )}
                    <div className="mt-3 space-y-2.5">
                      {p.examples.map((ex, i) => (
                        <div
                          key={i}
                          className="flex items-start gap-2 rounded-xl bg-slate-50 p-3"
                        >
                          <button
                            onClick={() => playSentence(ex.en).catch(() => {})}
                            className="mt-0.5 shrink-0 text-brand"
                          >
                            🔊
                          </button>
                          <div>
                            <p className="text-sm font-medium text-slate-800">
                              {ex.en}
                            </p>
                            <p className="mt-0.5 text-xs text-slate-500">
                              {ex.zh}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
