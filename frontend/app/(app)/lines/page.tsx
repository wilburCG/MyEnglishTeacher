"use client";

import { useEffect, useState } from "react";
import { playSentence } from "@/lib/audio";
import {
  episodeTag,
  listLines,
  MovieLine,
  setContentFavorite,
} from "@/lib/content";
import { levelLabel } from "@/lib/levels";

const LEVEL_COLORS: Record<string, string> = {
  "junior-g7": "bg-emerald-100 text-emerald-700",
  junior: "bg-sky-100 text-sky-700",
  senior: "bg-violet-100 text-violet-700",
  cet4: "bg-amber-100 text-amber-700",
  cet6: "bg-orange-100 text-orange-700",
  ielts: "bg-rose-100 text-rose-700",
};

export default function LinesPage() {
  const [lines, setLines] = useState<MovieLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [allLevels, setAllLevels] = useState(false);
  const [q, setQ] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [favs, setFavs] = useState<Record<number, boolean>>({});

  function load(includeAll: boolean, keyword: string) {
    setLoading(true);
    listLines({ includeAll, q: keyword.trim() || undefined })
      .then((list) => {
        setLines(list);
        setFavs(Object.fromEntries(list.map((l) => [l.id, l.favorite])));
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load(allLevels, q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allLevels]);

  async function toggleFav(l: MovieLine) {
    const next = !favs[l.id];
    setFavs((m) => ({ ...m, [l.id]: next }));
    await setContentFavorite("line", l.id, next).catch(() => {});
  }

  return (
    <div className="px-5 pt-8">
      <header>
        <h1 className="text-xl font-bold">
          🎬 Friends <span className="text-slate-400">老友记台词</span>
        </h1>
        <p className="mt-0.5 text-sm text-slate-500">
          精选短句 · 出处署名 · 点句子听发音
        </p>
      </header>

      <div className="mt-4 flex gap-2">
        <input
          className="flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand"
          placeholder="搜索英文台词"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load(allLevels, q)}
        />
        <button
          onClick={() => load(allLevels, q)}
          className="rounded-xl bg-brand px-4 text-sm font-medium text-white"
        >
          搜索
        </button>
      </div>

      <button
        onClick={() => setAllLevels((v) => !v)}
        className="mt-3 rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600"
      >
        {allLevels ? "只看本级别" : "显示全部级别"}
      </button>

      {loading ? (
        <p className="py-16 text-center text-slate-400">加载中…</p>
      ) : lines.length === 0 ? (
        <p className="py-16 text-center text-slate-400">没有匹配的台词</p>
      ) : (
        <div className="mt-4 space-y-3 pb-6">
          {lines.map((l) => {
            const open = openId === l.id;
            return (
              <div
                key={l.id}
                className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
              >
                <div className="bg-amber-50/60 px-4 py-2 text-xs text-slate-500">
                  <span className="font-semibold text-amber-700">
                    {l.character}
                  </span>
                  <span className="mx-2">·</span>
                  <span>{episodeTag(l)}</span>
                  <span
                    className={`ml-2 rounded px-1.5 py-0.5 ${
                      LEVEL_COLORS[l.level] ?? "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {levelLabel(l.level)}
                  </span>
                </div>

                <div className="p-4">
                  <div className="flex items-start gap-2">
                    <button
                      onClick={() => playSentence(l.text_en).catch(() => {})}
                      className="mt-1 shrink-0 text-lg"
                    >
                      🔊
                    </button>
                    <p
                      className="flex-1 cursor-pointer text-lg font-semibold leading-snug text-slate-800"
                      onClick={() => setOpenId(open ? null : l.id)}
                    >
                      {l.text_en}
                    </p>
                    <button
                      onClick={() => toggleFav(l)}
                      className="text-xl"
                    >
                      {favs[l.id] ? "⭐" : "☆"}
                    </button>
                  </div>

                  {open && (
                    <div className="mt-3 border-t border-slate-100 pt-3">
                      <p className="text-sm text-slate-600">{l.text_zh}</p>
                      {l.note_zh && (
                        <p className="mt-2 rounded-xl bg-slate-50 p-3 text-xs leading-relaxed text-slate-500">
                          💡 {l.note_zh}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
