import DOMPurify from "dompurify";
import { marked } from "marked";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

export function Markdown({ text, className = "" }: { text: string; className?: string }) {
  const html = DOMPurify.sanitize(marked.parse(text || "", { async: false }) as string);
  return <div className={`md ${className}`} dangerouslySetInnerHTML={{ __html: html }} />;
}

const TAGS: Record<string, string> = {
  quente: "bg-rose-100 text-rose-700",
  morna: "bg-amber-100 text-amber-800",
  fria: "bg-sky-100 text-sky-700",
};
const TAG_LABEL: Record<string, string> = { quente: "Quente", morna: "Morna", fria: "Fria" };

export function TagBadge({ tag, score }: { tag: string; score: number | null }) {
  if (!tag) return null;
  return (
    <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium ${TAGS[tag] ?? "bg-slate-100"}`}>
      {TAG_LABEL[tag] ?? tag}
      {score != null && <span className="opacity-70">{score}</span>}
    </span>
  );
}

export function Badge({ children, tone = "slate", title }: { children: ReactNode; tone?: "slate" | "amber" | "red" | "green" | "indigo"; title?: string }) {
  const tones = {
    slate: "bg-slate-100 text-slate-600",
    amber: "bg-amber-100 text-amber-800",
    red: "bg-red-100 text-red-700",
    green: "bg-green-100 text-green-700",
    indigo: "bg-indigo-100 text-indigo-700",
  };
  return (
    <span title={title} className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function Button({
  children, onClick, variant = "primary", disabled, type = "button", className = "",
}: {
  children: ReactNode; onClick?: () => void; variant?: "primary" | "ghost" | "outline"; disabled?: boolean;
  type?: "button" | "submit"; className?: string;
}) {
  const v = {
    primary: "bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-indigo-300",
    outline: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50",
    ghost: "text-slate-600 hover:bg-slate-100 disabled:opacity-50",
  }[variant];
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition ${v} ${className}`}>
      {children}
    </button>
  );
}

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return <span className={`inline-block animate-spin rounded-full border-2 border-current border-r-transparent ${className}`} />;
}

// ---------------------------------------------------------------- toasts

type Toast = { id: number; text: string; tone: "ok" | "erro" | "info" };
const ToastCtx = createContext<(text: string, tone?: Toast["tone"]) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: Toast["tone"] = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);
  const icon = { ok: "✅", erro: "⚠️", info: "🔄" };
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 left-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id} className="flex items-center gap-2 rounded-xl border border-slate-100 bg-white px-4 py-3 text-sm text-slate-700 shadow-lg">
            <span>{icon[t.tone]}</span>
            {t.text}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);

/** Diferença simples por linha: linhas novas em verde, removidas em vermelho riscado. */
export function LineDiff({ base, novo, resumo = "" }: { base: string; novo: string; resumo?: string }) {
  const norm = (s: string) => s.trim().replace(/\s+/g, " ");
  const b = base.split("\n").filter((l) => l.trim());
  const n = novo.split("\n").filter((l) => l.trim());
  const bs = new Set(b.map(norm));
  const ns = new Set(n.map(norm));
  return (
    <div className="space-y-3">
      {resumo && <Markdown text={resumo} />}
      <div className="font-mono text-[11px] leading-relaxed">
        {n.map((l, i) => <div key={`n${i}`} className={bs.has(norm(l)) ? "text-slate-500" : "diff-add"}>{bs.has(norm(l)) ? "  " : "+ "}{l}</div>)}
        {b.filter((l) => !ns.has(norm(l))).map((l, i) => <div key={`b${i}`} className="diff-del">- {l}</div>)}
      </div>
    </div>
  );
}
