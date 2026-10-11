"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { playSentence } from "@/lib/audio";
import {
  deleteReviewItem,
  KIND_LABEL,
  listReviewItems,
  resolveReviewItem,
  ReviewItem,
} from "@/lib/conversation";

export default function ReviewBookPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [showResolved, setShowResolved] = useState(false);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const r = await listReviewItems(showResolved);
    setItems(r.items);
    setLoading(false);
  }

  useEffect(() => {
    load().catch(() => setLoading(false));
  }, [showResolved]);

  return (
    <div className="px-5 pt-8 pb-8">
      <Link href="/speak" className="text-sm text-slate-400">
        ← 返回对话
      </Link>
      <h1 className="mt-3 text-xl font-bold">错句复习本</h1>
      <p className="mt-1 text-sm text-slate-500">
        AI 对话纠错与句子听写中的错误片段，可重听、标记掌握。
      </p>
      <Link
        href="/sdictation?source=review"
        className="mt-4 block rounded-2xl bg-brand py-3 text-center text-sm font-medium text-white"
      >
        🎧 错句重听：连续听对两次即掌握
      </Link>

      <div className="mt-4 flex rounded-xl bg-slate-100 p-1 text-sm">
        {[false, true].map((v) => (
          <button
            key={String(v)}
            onClick={() => setShowResolved(v)}
            className={`flex-1 rounded-lg py-2 ${
              showResolved === v ? "bg-white font-medium text-brand shadow-sm" : "text-slate-500"
            }`}
          >
            {v ? "已掌握" : "待复习"}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="mt-10 text-center text-sm text-slate-400">加载中…</p>
      ) : items.length === 0 ? (
        <div className="mt-12 rounded-3xl border border-dashed border-slate-200 bg-white p-10 text-center">
          <p className="text-3xl">🎉</p>
          <p className="mt-2 text-sm text-slate-500">
            {showResolved ? "还没有已掌握的项目" : "暂无待复习错误，去完成一场对话吧"}
          </p>
          <Link
            href="/speak"
            className="mt-4 inline-block rounded-xl bg-brand px-5 py-2.5 text-sm font-medium text-white"
          >
            开始对话
          </Link>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {items.map((item) => (
            <article key={item.id} className="rounded-2xl border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="rounded-full bg-red-50 px-2.5 py-1 text-xs text-red-600">
                  {KIND_LABEL[item.item_kind || ""] || "语法"}
                </span>
                <span className="truncate text-xs text-slate-400">{item.title}</span>
              </div>
              <p className="mt-3 text-sm leading-6">
                <span className="rounded bg-red-50 px-1.5 py-0.5 text-red-600 line-through">
                  {item.original}
                </span>
                <span className="mx-2 text-slate-400">→</span>
                <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-emerald-700">
                  {item.corrected}
                </span>
              </p>
              {item.explanation_zh && (
                <p className="mt-2 text-xs leading-5 text-slate-500">{item.explanation_zh}</p>
              )}
              {item.context_sentence && (
                <button
                  onClick={() => playSentence(item.context_sentence!).catch(() => {})}
                  className="mt-3 text-xs text-brand"
                >
                  🔊 听原句
                </button>
              )}
              <div className="mt-3 flex gap-2 border-t border-slate-100 pt-3 text-xs">
                {!item.is_resolved && (
                  <button
                    onClick={async () => {
                      await resolveReviewItem(item.id, true);
                      setItems((list) => list.filter((x) => x.id !== item.id));
                    }}
                    className="rounded-lg bg-emerald-50 px-3 py-1.5 text-emerald-700"
                  >
                    已掌握
                  </button>
                )}
                <button
                  onClick={async () => {
                    await deleteReviewItem(item.id);
                    setItems((list) => list.filter((x) => x.id !== item.id));
                  }}
                  className="ml-auto rounded-lg px-3 py-1.5 text-slate-400"
                >
                  删除
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
