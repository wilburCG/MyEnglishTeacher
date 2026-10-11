"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, getUser } from "@/lib/api";
import { levelLabel } from "@/lib/levels";

type Summary = {
  level: string;
  daily_new_goal: number;
  learned: number;
  mastered: number;
  due: number;
  favorites: number;
  streak_days: number;
  today_reviews: number;
  today_correct: number;
  today_accuracy: number | null;
};

type Queue = { counts: { due: number; new: number } };

export default function HomePage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [queue, setQueue] = useState<Queue | null>(null);
  const user = getUser();

  useEffect(() => {
    api<Summary>("/learn/summary").then(setSummary).catch(() => {});
    api<Queue>("/learn/queue").then(setQueue).catch(() => {});
  }, []);

  const remaining =
    (queue?.counts.due ?? 0) + (queue?.counts.new ?? 0);

  return (
    <div className="px-5 pt-8">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-500">Hi，{user?.display_name}</p>
          <h1 className="text-xl font-bold">今天也要加油 👋</h1>
        </div>
        <span className="rounded-full bg-orange-100 px-3 py-1 text-sm font-medium text-orange-600">
          🔥 {summary?.streak_days ?? 0} 天
        </span>
      </header>

      <div className="mt-5 rounded-3xl bg-brand p-6 text-white shadow-lg shadow-brand/30">
        <p className="text-sm opacity-90">
          {levelLabel(summary?.level ?? "junior-g7")} · 今日新词目标{" "}
          {summary?.daily_new_goal ?? 10} 个
        </p>
        <p className="mt-3 text-4xl font-bold">
          {remaining}
          <span className="ml-2 text-base font-normal opacity-90">
            个待学习
          </span>
        </p>
        <div className="mt-4 flex gap-3">
          <Link
            href="/learn"
            className={`flex-1 rounded-xl py-3 text-center font-medium ${
              remaining ? "bg-white text-brand" : "bg-white/30 text-white"
            }`}
          >
            {remaining ? "开始背单词" : "今日已完成 ✓"}
          </Link>
          <Link
            href="/dictation"
            className="rounded-xl bg-white/20 px-5 py-3 font-medium"
          >
            听写
          </Link>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-3">
        <Stat label="已学" value={summary?.learned ?? 0} />
        <Stat label="已掌握" value={summary?.mastered ?? 0} />
        <Stat label="收藏" value={summary?.favorites ?? 0} />
      </div>

      {summary?.today_reviews ? (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
          今天已复习 {summary.today_reviews} 次，正确率
          <span className="font-semibold text-emerald-600">
            {" "}
            {Math.round((summary.today_accuracy ?? 0) * 100)}%
          </span>
        </div>
      ) : null}

      <Link
        href="/speak"
        className="mt-4 block rounded-3xl border border-brand/15 bg-gradient-to-br from-brand to-indigo-500 p-5 text-white shadow-lg shadow-brand/20"
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm opacity-85">AI Speaking</p>
            <p className="mt-1 text-lg font-bold">和 AI 老师练对话</p>
            <p className="mt-1 text-xs opacity-85">实时纠错 · 错句入复习本 · 结课报告</p>
          </div>
          <span className="text-3xl">💬</span>
        </div>
      </Link>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <Link
          href="/patterns"
          className="rounded-2xl border border-slate-200 bg-white p-4"
        >
          <span className="text-2xl">✏️</span>
          <p className="mt-1 text-sm font-medium text-slate-700">典型句型</p>
          <p className="text-xs text-slate-400">24 个初一句型</p>
        </Link>
        <Link
          href="/lines"
          className="rounded-2xl border border-slate-200 bg-white p-4"
        >
          <span className="text-2xl">🎬</span>
          <p className="mt-1 text-sm font-medium text-slate-700">老友记台词</p>
          <p className="text-xs text-slate-400">经典名场面精讲</p>
        </Link>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 text-center">
      <p className="text-2xl font-bold text-slate-800">{value}</p>
      <p className="mt-0.5 text-xs text-slate-500">{label}</p>
    </div>
  );
}
