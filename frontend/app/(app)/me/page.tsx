"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, clearAuth, getUser, updateUser } from "@/lib/api";
import { playWord } from "@/lib/audio";
import { LEVELS, Level } from "@/lib/levels";

type Summary = {
  level: string;
  daily_new_goal: number;
  learned: number;
  mastered: number;
  due: number;
  favorites: number;
  streak_days: number;
};

type FavWord = {
  id: number;
  headword: string;
  phonetic: string | null;
  translation: string | null;
};

const GOALS = [5, 10, 15, 20, 30];

export default function MePage() {
  const router = useRouter();
  const user = getUser();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [favs, setFavs] = useState<FavWord[]>([]);
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
      const data = await api<{ words: FavWord[] }>("/favorites");
      setFavs(data.words);
    }
    setShowFavs(!showFavs);
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

      <Section title={`收藏单词 (${summary?.favorites ?? 0})`}>
        <button
          onClick={openFavs}
          className="w-full rounded-xl border border-slate-200 py-2.5 text-sm text-slate-600"
        >
          {showFavs ? "收起" : "查看收藏"}
        </button>
        {showFavs && (
          <ul className="mt-3 divide-y divide-slate-100">
            {favs.length === 0 && (
              <p className="py-3 text-center text-sm text-slate-400">
                还没有收藏
              </p>
            )}
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
      </Section>

      <button
        onClick={logout}
        className="mt-6 w-full rounded-xl border border-red-200 py-3 text-sm font-medium text-red-500"
      >
        退出登录
      </button>
      <p className="mt-6 text-center text-xs text-slate-300">
        MyEnglishTeacher · M1
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
