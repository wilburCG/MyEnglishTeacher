"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import { LEVELS, Level } from "@/lib/levels";
import { MovieLine, Pattern } from "@/lib/content";

type Tab = "pattern" | "line";

export default function AdminPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("pattern");
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [lines, setLines] = useState<MovieLine[]>([]);
  const [ready, setReady] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    const u = getUser();
    if (!u) {
      router.replace("/login");
      return;
    }
    if (u.role !== "admin") {
      router.replace("/");
      return;
    }
    setReady(true);
    api<{ patterns: Pattern[] }>("/patterns?include_all_levels=true")
      .then((r) => setPatterns(r.patterns));
    api<{ lines: MovieLine[] }>("/lines?include_all_levels=true")
      .then((r) => setLines(r.lines));
  }, [router]);

  async function del(type: Tab, id: number) {
    if (!confirm("确认删除？")) return;
    await api(`/admin/${type === "pattern" ? "patterns" : "lines"}/${id}`, {
      method: "DELETE",
    });
    setMsg("已删除");
    if (type === "pattern") setPatterns((l) => l.filter((x) => x.id !== id));
    else setLines((l) => l.filter((x) => x.id !== id));
  }

  if (!ready) return null;

  return (
    <div className="px-5 py-8">
      <h1 className="text-xl font-bold">内容管理</h1>
      <p className="mt-1 text-sm text-slate-500">
        句型与《老友记》台词的增删改（管理员）
      </p>
      {msg && <p className="mt-2 text-sm text-emerald-600">{msg}</p>}

      <div className="mt-4 flex gap-2 text-sm">
        {(["pattern", "line"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-full px-4 py-1.5 ${
              tab === t ? "bg-brand text-white" : "bg-slate-100 text-slate-600"
            }`}
          >
            {t === "pattern" ? `句型 (${patterns.length})` : `台词 (${lines.length})`}
          </button>
        ))}
      </div>

      {tab === "pattern" ? (
        <PatternForm
          key={`p-${patterns.length}`}
          onSaved={(p, isNew) => {
            setPatterns((l) => (isNew ? [...l, p] : l.map((x) => (x.id === p.id ? p : x))));
            setMsg("已保存");
          }}
        />
      ) : (
        <LineForm
          key={`l-${lines.length}`}
          onSaved={(l2, isNew) => {
            setLines((l) => (isNew ? [...l, l2] : l.map((x) => (x.id === l2.id ? l2 : x))));
            setMsg("已保存");
          }}
        />
      )}

      <h2 className="mt-8 text-sm font-semibold text-slate-700">
        已有内容（点击「编辑」载入表单）
      </h2>
      <div className="mt-3 space-y-2 pb-10">
        {tab === "pattern"
          ? patterns.map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3 text-sm"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium">{p.template}</p>
                  <p className="text-xs text-slate-400">
                    {p.level} · {p.theme} · {p.unit ?? "-"}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2 text-xs">
                  <button
                    className="text-brand"
                    onClick={() => {
                      const ev = new CustomEvent("met-edit", { detail: p });
                      window.dispatchEvent(ev);
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }}
                  >
                    编辑
                  </button>
                  <button className="text-red-500" onClick={() => del("pattern", p.id)}>
                    删除
                  </button>
                </div>
              </div>
            ))
          : lines.map((l) => (
              <div
                key={l.id}
                className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3 text-sm"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium">{l.text_en}</p>
                  <p className="text-xs text-slate-400">
                    {l.character} · {l.season ? `S${l.season}` : "-"}
                    {l.episode ? `E${l.episode}` : ""} · {l.level}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2 text-xs">
                  <button
                    className="text-brand"
                    onClick={() => {
                      const ev = new CustomEvent("met-edit", { detail: l });
                      window.dispatchEvent(ev);
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }}
                  >
                    编辑
                  </button>
                  <button className="text-red-500" onClick={() => del("line", l.id)}>
                    删除
                  </button>
                </div>
              </div>
            ))}
      </div>
    </div>
  );
}

const inputCls =
  "w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand";

function LevelSelect({ value, onChange }: { value: Level; onChange: (v: Level) => void }) {
  return (
    <select className={inputCls} value={value} onChange={(e) => onChange(e.target.value as Level)}>
      {LEVELS.map((l) => (
        <option key={l.value} value={l.value}>
          {l.label}（{l.sub}）
        </option>
      ))}
    </select>
  );
}

function PatternForm({
  onSaved,
}: {
  onSaved: (p: Pattern, isNew: boolean) => void;
}) {
  const blank = {
    id: null as number | null,
    level: "junior-g7" as Level,
    theme: "校园生活",
    unit: "",
    seq: 0,
    template: "",
    func_zh: "",
    grammar_point: "",
    explanation_zh: "",
    ex1_en: "",
    ex1_zh: "",
    ex2_en: "",
    ex2_zh: "",
  };
  const [f, setF] = useState(blank);
  const set = (k: string, v: any) => setF((x) => ({ ...x, [k]: v }));

  useEffect(() => {
    const h = (e: Event) => {
      const p = (e as CustomEvent).detail as Pattern;
      setF({
        id: p.id,
        level: p.level as Level,
        theme: p.theme,
        unit: p.unit ?? "",
        seq: 0,
        template: p.template,
        func_zh: p.func_zh,
        grammar_point: p.grammar_point ?? "",
        explanation_zh: p.explanation_zh ?? "",
        ex1_en: p.examples[0]?.en ?? "",
        ex1_zh: p.examples[0]?.zh ?? "",
        ex2_en: p.examples[1]?.en ?? "",
        ex2_zh: p.examples[1]?.zh ?? "",
      });
    };
    window.addEventListener("met-edit", h);
    return () => window.removeEventListener("met-edit", h);
  }, []);

  async function save() {
    const examples = [
      f.ex1_en ? { en: f.ex1_en, zh: f.ex1_zh } : null,
      f.ex2_en ? { en: f.ex2_en, zh: f.ex2_zh } : null,
    ].filter(Boolean);
    const body = {
      level: f.level,
      theme: f.theme,
      unit: f.unit || null,
      seq: Number(f.seq) || 0,
      template: f.template,
      func_zh: f.func_zh,
      grammar_point: f.grammar_point || null,
      explanation_zh: f.explanation_zh || null,
      examples,
      is_published: true,
    };
    const path = f.id ? `/admin/patterns/${f.id}` : "/admin/patterns";
    const p = (await api(path, {
      method: f.id ? "PATCH" : "POST",
      body: JSON.stringify(body),
    })) as Pattern;
    onSaved(p, !f.id);
    setF(blank);
  }

  return (
    <div className="mt-4 space-y-2 rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-sm font-semibold">{f.id ? `编辑 #${f.id}` : "新增句型"}</p>
      <LevelSelect value={f.level} onChange={(v) => set("level", v)} />
      <input className={inputCls} placeholder="主题（如 校园生活）" value={f.theme} onChange={(e) => set("theme", e.target.value)} />
      <input className={inputCls} placeholder="单元（如 Unit 1，可空）" value={f.unit} onChange={(e) => set("unit", e.target.value)} />
      <input className={inputCls} placeholder="排序序号（可留 0）" inputMode="numeric" value={f.seq} onChange={(e) => set("seq", e.target.value)} />
      <input className={inputCls} placeholder="句型模板，如 How much is ...?" value={f.template} onChange={(e) => set("template", e.target.value)} />
      <input className={inputCls} placeholder="功能（中文一句话）" value={f.func_zh} onChange={(e) => set("func_zh", e.target.value)} />
      <input className={inputCls} placeholder="语法点，如 how much 疑问句" value={f.grammar_point} onChange={(e) => set("grammar_point", e.target.value)} />
      <textarea className={inputCls} rows={2} placeholder="讲解（中文）" value={f.explanation_zh} onChange={(e) => set("explanation_zh", e.target.value)} />
      <div className="grid grid-cols-2 gap-2">
        <input className={inputCls} placeholder="例句 1 英文" value={f.ex1_en} onChange={(e) => set("ex1_en", e.target.value)} />
        <input className={inputCls} placeholder="例句 1 中文" value={f.ex1_zh} onChange={(e) => set("ex1_zh", e.target.value)} />
        <input className={inputCls} placeholder="例句 2 英文" value={f.ex2_en} onChange={(e) => set("ex2_en", e.target.value)} />
        <input className={inputCls} placeholder="例句 2 中文" value={f.ex2_zh} onChange={(e) => set("ex2_zh", e.target.value)} />
      </div>
      <div className="flex gap-2">
        <button onClick={save} className="flex-1 rounded-xl bg-brand py-2 text-sm font-medium text-white">
          {f.id ? "保存修改" : "新增"}
        </button>
        {f.id && (
          <button onClick={() => setF(blank)} className="rounded-xl border border-slate-300 px-4 text-sm">
            取消
          </button>
        )}
      </div>
    </div>
  );
}

function LineForm({ onSaved }: { onSaved: (l: MovieLine, isNew: boolean) => void }) {
  const blank = {
    id: null as number | null,
    level: "junior-g7" as Level,
    show: "Friends",
    season: "",
    episode: "",
    character: "",
    text_en: "",
    text_zh: "",
    theme: "",
    note_zh: "",
    seq: 0,
  };
  const [f, setF] = useState(blank);
  const set = (k: string, v: any) => setF((x) => ({ ...x, [k]: v }));

  useEffect(() => {
    const h = (e: Event) => {
      const l = (e as CustomEvent).detail as MovieLine;
      setF({
        id: l.id,
        level: l.level as Level,
        show: l.show,
        season: l.season ? String(l.season) : "",
        episode: l.episode ? String(l.episode) : "",
        character: l.character,
        text_en: l.text_en,
        text_zh: l.text_zh,
        theme: l.theme ?? "",
        note_zh: l.note_zh ?? "",
        seq: 0,
      });
    };
    window.addEventListener("met-edit", h);
    return () => window.removeEventListener("met-edit", h);
  }, []);

  async function save() {
    const body = {
      level: f.level,
      show: f.show || "Friends",
      season: f.season ? Number(f.season) : null,
      episode: f.episode ? Number(f.episode) : null,
      character: f.character,
      text_en: f.text_en,
      text_zh: f.text_zh,
      theme: f.theme || null,
      note_zh: f.note_zh || null,
      seq: Number(f.seq) || 0,
      is_published: true,
    };
    const path = f.id ? `/admin/lines/${f.id}` : "/admin/lines";
    const l = (await api(path, {
      method: f.id ? "PATCH" : "POST",
      body: JSON.stringify(body),
    })) as MovieLine;
    onSaved(l, !f.id);
    setF(blank);
  }

  return (
    <div className="mt-4 space-y-2 rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-sm font-semibold">{f.id ? `编辑 #${f.id}` : "新增台词"}</p>
      <LevelSelect value={f.level} onChange={(v) => set("level", v)} />
      <div className="grid grid-cols-3 gap-2">
        <input className={inputCls} placeholder="剧名" value={f.show} onChange={(e) => set("show", e.target.value)} />
        <input className={inputCls} placeholder="季（数字）" inputMode="numeric" value={f.season} onChange={(e) => set("season", e.target.value)} />
        <input className={inputCls} placeholder="集（数字）" inputMode="numeric" value={f.episode} onChange={(e) => set("episode", e.target.value)} />
      </div>
      <input className={inputCls} placeholder="角色，如 Ross" value={f.character} onChange={(e) => set("character", e.target.value)} />
      <input className={inputCls} placeholder="主题（可空）" value={f.theme} onChange={(e) => set("theme", e.target.value)} />
      <textarea className={inputCls} rows={2} placeholder="英文原句（短句）" value={f.text_en} onChange={(e) => set("text_en", e.target.value)} />
      <textarea className={inputCls} rows={2} placeholder="中文翻译" value={f.text_zh} onChange={(e) => set("text_zh", e.target.value)} />
      <textarea className={inputCls} rows={3} placeholder="语言点讲解（中文，可空）" value={f.note_zh} onChange={(e) => set("note_zh", e.target.value)} />
      <div className="flex gap-2">
        <button onClick={save} className="flex-1 rounded-xl bg-brand py-2 text-sm font-medium text-white">
          {f.id ? "保存修改" : "新增"}
        </button>
        {f.id && (
          <button onClick={() => setF(blank)} className="rounded-xl border border-slate-300 px-4 text-sm">
            取消
          </button>
        )}
      </div>
    </div>
  );
}
