import { useState, type ReactNode } from "react";

/** Lista de valores em texto livre: digite e Enter (ou vírgula) para adicionar. Sugestões viram atalhos. */
export function ChipsInput({
  value, onChange, placeholder = "digite e Enter", suggestions = [], tone = "slate",
}: {
  value: string[]; onChange: (v: string[]) => void; placeholder?: string; suggestions?: string[];
  tone?: "slate" | "red" | "green" | "indigo";
}) {
  const [draft, setDraft] = useState("");
  const add = (raw: string) => {
    const items = raw.split(/[,;\n]/).map((s) => s.trim()).filter(Boolean);
    const next = [...value];
    for (const it of items) if (!next.some((x) => x.toLowerCase() === it.toLowerCase())) next.push(it);
    onChange(next);
    setDraft("");
  };
  const tones = {
    slate: "bg-slate-100 text-slate-700",
    red: "bg-red-50 text-red-700",
    green: "bg-green-50 text-green-700",
    indigo: "bg-indigo-50 text-indigo-700",
  };
  const missing = suggestions.filter((s) => !value.some((v) => v.toLowerCase() === s.toLowerCase()));
  return (
    <div>
      <div className="flex min-h-9 flex-wrap items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-2 py-1.5 focus-within:border-indigo-400">
        {value.map((v, i) => (
          <span key={`${v}-${i}`} className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs ${tones[tone]}`}>
            {v}
            <button type="button" onClick={() => onChange(value.filter((_, j) => j !== i))} className="opacity-50 hover:opacity-100" aria-label={`remover ${v}`}>×</button>
          </span>
        ))}
        <input
          value={draft}
          onChange={(e) => (e.target.value.endsWith(",") ? add(e.target.value) : setDraft(e.target.value))}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); if (draft.trim()) add(draft); }
            if (e.key === "Backspace" && !draft && value.length) onChange(value.slice(0, -1));
          }}
          onBlur={() => draft.trim() && add(draft)}
          onPaste={(e) => { const t = e.clipboardData.getData("text"); if (/[,;\n]/.test(t)) { e.preventDefault(); add(t); } }}
          placeholder={value.length ? "" : placeholder}
          className="min-w-24 flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400"
        />
      </div>
      {missing.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {missing.map((s) => (
            <button key={s} type="button" onClick={() => onChange([...value, s])}
              className="rounded-md border border-dashed border-slate-300 px-1.5 py-0.5 text-[11px] text-slate-500 hover:border-indigo-400 hover:text-indigo-600">
              + {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function NumberInput({ value, onChange, prefix, suffix, placeholder, min = 0 }: {
  value: number | null; onChange: (v: number | null) => void; prefix?: string; suffix?: string; placeholder?: string; min?: number;
}) {
  return (
    <div className="flex items-center rounded-lg border border-slate-300 bg-white focus-within:border-indigo-400">
      {prefix && <span className="pl-2.5 text-sm text-slate-400">{prefix}</span>}
      <input type="number" min={min} value={value ?? ""} placeholder={placeholder ?? "sem limite"}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        className="w-full min-w-0 bg-transparent px-2.5 py-1.5 text-sm outline-none" />
      {suffix && <span className="pr-2.5 text-sm text-slate-400">{suffix}</span>}
    </div>
  );
}

export function Field({ label, hint, children, className = "" }: { label: string; hint?: string; children: ReactNode; className?: string }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11px] leading-snug text-slate-400">{hint}</span>}
    </label>
  );
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" onClick={() => onChange(!checked)} className="inline-flex items-center gap-2 text-sm text-slate-700">
      <span className={`relative h-5 w-9 rounded-full transition ${checked ? "bg-indigo-600" : "bg-slate-300"}`}>
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition ${checked ? "left-4.5" : "left-0.5"}`} />
      </span>
      {label}
    </button>
  );
}

export function Section({ title, desc, children, changed }: { title: string; desc?: string; children: ReactNode; changed?: boolean }) {
  return (
    <section className={`rounded-2xl border bg-white p-5 transition ${changed ? "border-amber-300 ring-2 ring-amber-100" : "border-slate-200"}`}>
      <div className="mb-4 flex items-start gap-2">
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          {desc && <p className="mt-0.5 text-xs text-slate-500">{desc}</p>}
        </div>
        {changed && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-medium text-amber-800">alterado pela IA</span>}
      </div>
      {children}
    </section>
  );
}
