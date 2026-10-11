"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, setAuth } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await api("/auth/phone", {
        method: "POST",
        body: JSON.stringify({
          phone: phone.trim(),
          display_name: name.trim() || undefined,
        }),
      });
      setAuth(data.token, data.user);
      router.replace("/");
    } catch (err: any) {
      setError(err.message || "登录失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-6">
      <div className="text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-brand text-3xl text-white shadow">
          🎓
        </div>
        <h1 className="mt-4 text-2xl font-bold">MyEnglishTeacher</h1>
        <p className="mt-1 text-sm text-slate-500">你的随身 AI 英语私教</p>
      </div>

      <form onSubmit={submit} className="mt-8 space-y-3">
        <input
          className="w-full rounded-xl border border-slate-300 px-4 py-3.5 text-lg outline-none focus:border-brand"
          placeholder="手机号"
          inputMode="numeric"
          maxLength={11}
          value={phone}
          onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
        />
        <input
          className="w-full rounded-xl border border-slate-300 px-4 py-3.5 outline-none focus:border-brand"
          placeholder="昵称（首次进入填写）"
          maxLength={32}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          disabled={loading || phone.length !== 11}
          className="w-full rounded-xl bg-brand py-3.5 text-lg font-medium text-white disabled:bg-slate-300"
        >
          {loading ? "进入中…" : "一键进入"}
        </button>
      </form>
      <p className="mt-6 text-center text-xs text-slate-400">
        无需验证码，手机号即账号
      </p>
    </main>
  );
}
