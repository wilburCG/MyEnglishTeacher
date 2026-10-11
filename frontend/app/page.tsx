"use client";

import { useEffect, useState } from "react";

type Health = { status: string; db: string; model: string };

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch("/api/v1/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setError(true));
  }, []);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col px-5 py-10">
      <div className="rounded-3xl bg-brand p-7 text-white shadow-lg">
        <p className="text-sm/none opacity-80">M0 脚手架已就绪</p>
        <h1 className="mt-3 text-3xl font-bold tracking-tight">
          MyEnglishTeacher
        </h1>
        <p className="mt-2 text-sm opacity-90">你的随身 AI 英语私教 · 初一起步</p>
      </div>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 text-sm">
        <p className="font-semibold text-slate-700">后端连接状态</p>
        {error ? (
          <p className="mt-2 text-red-600">后端未连通</p>
        ) : health ? (
          <ul className="mt-2 space-y-1 text-slate-600">
            <li>API：{health.status}</li>
            <li>数据库：{health.db}</li>
            <li>模型：{health.model}</li>
          </ul>
        ) : (
          <p className="mt-2 text-slate-400">检测中…</p>
        )}
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3 text-sm">
        {["背单词", "句型", "老友记台词", "AI 对话", "专项听写", "跟读评分"].map(
          (name, i) => (
            <div
              key={name}
              className="rounded-2xl border border-slate-200 bg-white p-4 text-slate-700"
            >
              <span className="text-lg">{["📖", "✏️", "🎬", "💬", "🎧", "🎤"][i]}</span>
              <p className="mt-1 font-medium">{name}</p>
            </div>
          ),
        )}
      </div>

      <p className="mt-auto pt-10 text-center text-xs text-slate-400">
        v0.1 · M0 scaffold
      </p>
    </main>
  );
}
