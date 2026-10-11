"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Conversation,
  listConversations,
  listScenarios,
  Scenario,
  startConversation,
} from "@/lib/conversation";
import { levelLabel } from "@/lib/levels";

export default function SpeakHomePage() {
  const router = useRouter();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState<number | null>(null);
  const [err, setErr] = useState("");

  async function load() {
    const [s, c] = await Promise.all([listScenarios(), listConversations()]);
    setScenarios(s.scenarios);
    setConversations(c.conversations);
    setLoading(false);
  }

  useEffect(() => {
    load().catch((e) => {
      setErr(e.message);
      setLoading(false);
    });
  }, []);

  async function enter(s: Scenario) {
    setStarting(s.id);
    setErr("");
    try {
      const c = await startConversation(s.id);
      router.push(`/speak/${c.id}`);
    } catch (e: any) {
      setErr(e.message || "开启失败");
      setStarting(null);
    }
  }

  const active = conversations.filter((c) => c.status === "active");

  return (
    <div className="px-5 pt-8">
      <header>
        <p className="text-sm text-slate-500">AI Speaking Practice</p>
        <h1 className="text-xl font-bold">AI 虚拟老师对话</h1>
        <p className="mt-1 text-sm leading-6 text-slate-500">
          全程英语角色扮演，每句话自动纠错；错误可一键加入复习本。
        </p>
      </header>

      <Link
        href="/review"
        className="mt-4 flex items-center justify-between rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
      >
        <span>📒 错句复习本</span>
        <span>查看 →</span>
      </Link>

      {active.length > 0 && (
        <section className="mt-6">
          <h2 className="text-sm font-semibold text-slate-700">继续上一场</h2>
          <div className="mt-2 space-y-2">
            {active.slice(0, 3).map((c) => (
              <Link
                key={c.id}
                href={`/speak/${c.id}`}
                className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white p-4"
              >
                <div>
                  <p className="text-sm font-medium">{c.title_zh}</p>
                  <p className="text-xs text-slate-400">
                    {c.turn_count} 轮 · {levelLabel(c.level)}
                  </p>
                </div>
                <span className="text-sm text-brand">继续 →</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="mt-6">
        <h2 className="text-sm font-semibold text-slate-700">选择场景</h2>
        {loading && <p className="mt-6 text-center text-sm text-slate-400">加载中…</p>}
        {!loading && scenarios.length === 0 && (
          <p className="mt-6 rounded-2xl bg-white p-5 text-center text-sm text-slate-400">
            当前级别场景正在准备中，先切换到初一体验吧。
          </p>
        )}
        <div className="mt-3 space-y-3 pb-6">
          {scenarios.map((s) => (
            <article
              key={s.id}
              className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-medium text-brand">{s.theme}</p>
                  <h3 className="mt-1 font-semibold text-slate-800">{s.title_zh}</h3>
                  <p className="text-xs text-slate-400">
                    {s.title_en} · {levelLabel(s.level)} · 难度 {"★".repeat(s.difficulty)}
                  </p>
                </div>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-500">
                  {s.recommended_words.length} 词
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-600">{s.description_zh}</p>
              <div className="mt-3 rounded-2xl bg-slate-50 p-3">
                <p className="text-xs font-medium text-slate-500">任务目标</p>
                <p className="mt-1 text-sm text-slate-700">{s.goal}</p>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {s.recommended_words.map((w) => (
                  <span
                    key={w}
                    className="rounded-full bg-brand/10 px-2.5 py-1 text-xs text-brand"
                  >
                    {w}
                  </span>
                ))}
              </div>
              <button
                onClick={() => enter(s)}
                disabled={starting !== null}
                className="mt-4 w-full rounded-xl bg-brand py-3 text-sm font-medium text-white disabled:opacity-60"
              >
                {starting === s.id ? "正在进入…" : "开始对话"}
              </button>
            </article>
          ))}
        </div>
      </section>

      {err && <p className="pb-8 text-center text-sm text-red-500">{err}</p>}
    </div>
  );
}
