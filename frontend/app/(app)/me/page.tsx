"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, clearAuth, getUser, updateUser } from "@/lib/api";
import { playSentence, playWord } from "@/lib/audio";
import {
  episodeTag,
  MovieLine,
  Pattern,
  setContentFavorite,
} from "@/lib/content";
import { LEVELS, Level } from "@/lib/levels";

type Summary = {
  level: string;
  daily_new_goal: number;
  learned: number;
  mastered: number;
  due: number;
  favorites: number;
  content_favorites: number;
  streak_days: number;
};

type FavWord = {
  id: number;
  headword: string;
  phonetic: string | null;
  translation: string | null;
};

type FavTab = "word" | "pattern" | "line";

const GOALS = [5, 10, 15, 20, 30];

export default function MePage() {
  const router = useRouter();
  const user = getUser();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [favs, setFavs] = useState<FavWord[]>([]);
  const [favPatterns, setFavPatterns] = useState<Pattern[]>([]);
  const [favLines, setFavLines] = useState<MovieLine[]>([]);
  const [favTab, setFavTab] = useState<FavTab>("word");
  const [showFavs, setShowFavs] = useState(false);

  useEffect(() => {
    api<Summary>("/learn/summary").then(setSummary).catch(() => {});
  }, []);

  async function setLevel(level: Level) {
    const u = await api("/auth/me", {
      method: "PATCH",
      body: JSON.stringify({ level }),
    });
    updateUser(u);
    setSummary((s) => (s ? { ...s, level } : s));
  }

  async function setGoal(daily_new_goal: number) {
    const u = await api("/auth/me", {
      method: "PATCH",
      body: JSON.stringify({ daily_new_goal }),
    });
    updateUser(u);
    setSummary((s) => (s ? { ...s, daily_new_goal } : s));
  }

  async function openFavs() {
    if (!showFavs) {
      const [w, p, l] = await Promise.all([
        api<{ words: FavWord[] }>("/favorites"),
        api<{ patterns: Pattern[] }>("/content/favorites?item_type=pattern"),
        api<{ lines: MovieLine[] }>("/content/favorites?item_type=line"),
      ]);
      setFavs(w.words);
      setFavPatterns(p.patterns);
      setFavLines(l.lines);
    }
    setShowFavs(!showFavs);
  }

  async function unfav(
    type: FavTab,
    id: number,
  ) {
    if (type === "pattern") {
      await setContentFavorite("pattern", id, false);
      setFavPatterns((list) => list.filter((x) => x.id !== id));
    } else {
      await setContentFavorite("line", id, false);
      setFavLines((list) => list.filter((x) => x.id !== id));
    }
  }

  function logout() {
    clearAuth();
    router.replace("/login");
  }

  return (
    <div className="px-5 pt-8">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand/10 text-xl">
          {user?.display_name?.[0] ?? "U"}
        </div>
        <div>
          <p className="font-semibold">{user?.display_name}</p>
          <p className="text-xs text-slate-400">{user?.phone}</p>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-4 gap-2 text-center">
        <Metric label="连续" value={`${summary?.streak_days ?? 0}天`} />
        <Metric label="已学" value={summary?.learned ?? 0} />
        <Metric label="掌握" value={summary?.mastered ?? 0} />
        <Metric label="待复习" value={summary?.due ?? 0} />
      </div>

      <Section title="当前级别">
        <div className="grid grid-cols-3 gap-2">
          {LEVELS.map((l) => (
            <button
              key={l.value}
              onClick={() => setLevel(l.value)}
              className={`rounded-xl border px-2 py-2.5 text-sm ${
                (summary?.level ?? user?.level) === l.value
                  ? "border-brand bg-brand/5 font-medium text-brand"
                  : "border-slate-200 text-slate-600"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-slate-400">
          {LEVELS.find(
            (l) => l.value === (summary?.level ?? user?.level),
          )?.sub}
        </p>
      </Section>

      <Section title="每日新词目标">
        <div className="flex gap-2">
          {GOALS.map((g) => (
            <button
              key={g}
              onClick={() => setGoal(g)}
              className={`flex-1 rounded-xl border py-2 text-sm ${
                summary?.daily_new_goal === g
                  ? "border-brand bg-brand/5 font-medium text-brand"
                  : "border-slate-200 text-slate-600"
              }`}
            >
              {g}
            </button>
          ))}
        </div>
      </Section>

      <Section
        title={`我的收藏 (${
          (summary?.favorites ?? 0) + (summary?.content_favorites ?? 0)
        })`}
      >
        <button
          onClick={openFavs}
          className="w-full rounded-xl border border-slate-200 py-2.5 text-sm text-slate-600"
        >
          {showFavs ? "收起" : "查看收藏"}
        </button>
        {showFavs && (
          <div className="mt-3">
            <div className="flex gap-2 text-xs">
              {([
                ["word", `单词 ${favs.length}`],
                ["pattern", `句型 ${favPatterns.length}`],
                ["line", `台词 ${favLines.length}`],
              ] as [FavTab, string][]).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setFavTab(key)}
                  className={`rounded-full px-3 py-1 ${
                    favTab === key
                      ? "bg-brand text-white"
                      : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {favTab === "word" && (
              <ul className="mt-3 divide-y divide-slate-100">
                {favs.length === 0 && <Empty />}
                {favs.map((w) => (
                  <li key={w.id} className="flex items-center gap-3 py-2.5">
                    <button
                      onClick={() => playWord(w.id).catch(() => {})}
                      className="text-brand"
                    >
                      🔊
                    </button>
                    <div>
                      <p className="text-sm font-medium">{w.headword}</p>
                      <p className="text-xs text-slate-400">{w.phonetic}</p>
                    </div>
                    <p className="ml-auto truncate text-sm text-slate-500">
                      {w.translation?.split("\n")[0]}
                    </p>
                  </li>
                ))}
              </ul>
            )}

            {favTab === "pattern" && (
              <ul className="mt-3 space-y-2">
                {favPatterns.length === 0 && <Empty />}
                {favPatterns.map((p) => (
                  <li
                    key={p.id}
                    className="flex items-start gap-2 rounded-xl bg-slate-50 p-3"
                  >
                    <button
                      onClick={() =>
                        playSentence(p.examples[0]?.en ?? p.template).catch(
                          () => {},
                        )
                      }
                      className="mt-0.5 text-brand"
                    >
                      🔊
                    </button>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-800">
                        {p.template}
                      </p>
                      <p className="text-xs text-slate-500">{p.func_zh}</p>
                    </div>
                    <button
                      onClick={() => unfav("pattern", p.id)}
                      className="text-xs text-slate-400"
                    >
                      移除
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {favTab === "line" && (
              <ul className="mt-3 space-y-2">
                {favLines.length === 0 && <Empty />}
                {favLines.map((l) => (
                  <li
                    key={l.id}
                    className="flex items-start gap-2 rounded-xl bg-amber-50/60 p-3"
                  >
                    <button
                      onClick={() => playSentence(l.text_en).catch(() => {})}
                      className="mt-0.5 text-brand"
                    >
                      🔊
                    </button>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-800">
                        {l.text_en}
                      </p>
                      <p className="text-xs text-slate-500">
                        {l.character} · {episodeTag(l)}
                      </p>
                    </div>
                    <button
                      onClick={() => unfav("line", l.id)}
                      className="text-xs text-slate-400"
                    >
                      移除
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </Section>

      <Link
        href="/review"
        className="mt-6 block w-full rounded-xl border border-amber-200 bg-amber-50 py-3 text-center text-sm font-medium text-amber-800"
      >
        📒 错句复习本
      </Link>

      {user?.role === "admin" && (
        <Link
          href="/admin"
          className="mt-6 block w-full rounded-xl border border-brand py-3 text-center text-sm font-medium text-brand"
        >
          🛠 内容管理后台
        </Link>
      )}

      <button
        onClick={logout}
        className="mt-3 w-full rounded-xl border border-red-200 py-3 text-sm font-medium text-red-500"
      >
        退出登录
      </button>
      <p className="mt-6 text-center text-xs text-slate-300">
        MyEnglishTeacher · M3
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white py-3">
      <p className="text-lg font-bold">{value}</p>
      <p className="text-xs text-slate-400">{label}</p>
    </div>
  );
}

function Empty() {
  return (
    <p className="py-3 text-center text-sm text-slate-400">还没有收藏</p>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-700">{title}</h2>
      {children}
    </section>
  );
}
