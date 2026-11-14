import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Button, Spinner } from "./ui";

export interface Draft { fatos_yaml: string; cv_base_md: string; regras_cv: string }
type Msg = { role: "user" | "ia"; text: string; mudancas?: string[]; perguntas?: string[]; erro?: boolean };

interface ChatOut {
  resposta: string;
  alterou_fatos: boolean;
  alterou_cv: boolean;
  alterou_regras: boolean;
  regras_cv: string;
  fatos_yaml: string;
  cv_base_md: string;
  mudancas: string[];
  perguntas: string[];
}

const EXEMPLOS = [
  "Me pergunte o que falta para completar meu CV",
  "Os dashboards que fiz são usados por 12 pessoas do Marketing e atualizam todo dia",
  "Tira o projeto da faculdade do CV",
  "Muda o título para Analista de Dados",
  "A partir de agora, não use a fórmula XYZ nos CVs adaptados",
];

/** Chat para informar fatos e pedir alterações. Trabalha sobre o rascunho; quem salva é o pai. */
export default function CVChat({ atual, onDraft }: { atual: Draft; onDraft: (d: Draft) => void }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [texto, setTexto] = useState("");
  const [pensando, setPensando] = useState(false);
  const fim = useRef<HTMLDivElement>(null);
  const campo = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    fim.current?.scrollIntoView({ block: "nearest" });
  }, [msgs, pensando]);

  async function enviar(msg?: string) {
    const t = (msg ?? texto).trim();
    if (!t || pensando) return;
    const historico = msgs.filter((m) => !m.erro).map((m) => ({ role: m.role === "ia" ? "assistant" : "user", text: m.text }));
    setMsgs((m) => [...m, { role: "user", text: t }]);
    setTexto("");
    setPensando(true);
    try {
      const r = await api<ChatOut>("/profile/cv-chat", {
        method: "POST",
        body: { mensagem: t, historico, fatos_yaml: atual.fatos_yaml, cv_base_md: atual.cv_base_md, regras_cv: atual.regras_cv },
      });
      if (r.alterou_fatos || r.alterou_cv || r.alterou_regras) onDraft({ fatos_yaml: r.fatos_yaml, cv_base_md: r.cv_base_md, regras_cv: r.regras_cv });
      setMsgs((m) => [...m, { role: "ia", text: r.resposta, mudancas: r.mudancas, perguntas: r.perguntas }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "ia", text: `Não consegui: ${(e as Error).message}`, erro: true }]);
    } finally {
      setPensando(false);
    }
  }

  function responder(pergunta: string) {
    setTexto(`Sobre "${pergunta}": `);
    campo.current?.focus();
  }

  return (
    <section className="rounded-2xl border border-indigo-200 bg-gradient-to-b from-indigo-50/70 to-white p-5">
      <h3 className="text-sm font-semibold text-slate-900">💬 Converse sobre o seu CV</h3>
      <p className="mt-0.5 text-xs text-slate-500">
        Conte números e fatos que faltam, peça mudanças no CV base ou diga como quer que os CVs adaptados sejam escritos. A IA atualiza tudo, e você confere antes de salvar.
      </p>

      {msgs.length === 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {EXEMPLOS.map((e) => (
            <button key={e} onClick={() => (e.startsWith("Me pergunte") ? enviar(e) : setTexto(e))}
              className="rounded-full border border-indigo-200 bg-white px-3 py-1 text-xs text-indigo-700 hover:bg-indigo-50">
              {e}
            </button>
          ))}
        </div>
      ) : (
        <div className="mt-3 max-h-80 space-y-2 overflow-y-auto pr-1">
          {msgs.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[88%] rounded-2xl px-3.5 py-2 text-sm ${m.role === "user" ? "bg-indigo-600 text-white" : m.erro ? "border border-red-200 bg-red-50 text-red-700" : "border border-slate-200 bg-white text-slate-700"}`}>
                <p className="whitespace-pre-wrap">{m.text}</p>
                {m.mudancas && m.mudancas.length > 0 && (
                  <ul className="mt-1.5 space-y-0.5 border-t border-slate-100 pt-1.5 text-xs text-slate-600">
                    {m.mudancas.map((x, j) => <li key={j}>✏️ {x}</li>)}
                  </ul>
                )}
                {m.perguntas && m.perguntas.length > 0 && (
                  <div className="mt-1.5 space-y-1 border-t border-slate-100 pt-1.5">
                    {m.perguntas.map((q, j) => (
                      <button key={j} onClick={() => responder(q)} title="Responder"
                        className="block w-full rounded-lg bg-slate-50 px-2 py-1 text-left text-xs text-slate-600 hover:bg-indigo-50 hover:text-indigo-700">
                        ❓ {q}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {pensando && (
            <div className="flex">
              <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3.5 py-2 text-sm text-slate-500">
                <Spinner /> atualizando fatos e CV… (até 1 min)
              </div>
            </div>
          )}
          <div ref={fim} />
        </div>
      )}

      <div className="mt-3 flex items-end gap-2">
        <textarea
          ref={campo}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(); } }}
          rows={2}
          placeholder="Ex.: a automação em Python reduziu o relatório semanal de 3 h para 20 min"
          className="flex-1 resize-none rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-400"
        />
        <Button onClick={() => enviar()} disabled={!texto.trim() || pensando} className="h-10">
          {pensando ? <Spinner /> : "Enviar"}
        </Button>
      </div>
    </section>
  );
}
