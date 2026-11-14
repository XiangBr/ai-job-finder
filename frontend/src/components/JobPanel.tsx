import { useEffect, useRef, useState } from "react";
import { api, COLUNAS, relTime, salario, type CV, type JobDetail } from "../api";
import { Badge, Button, LineDiff, Markdown, Spinner, TagBadge, useToast } from "./ui";

const CLASS_TONE = { forte: "green", parcial: "amber", lacuna: "red", bloqueio: "red" } as const;
const MODELO = { remoto: "Remoto", hibrido: "Híbrido", presencial: "Presencial" } as Record<string, string>;

export default function JobPanel({ jobId, onClose, onChange }: { jobId: number; onClose: () => void; onChange: () => void }) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [cv, setCv] = useState<CV | null>(null);
  const [gerando, setGerando] = useState(false);
  const [reanalisando, setReanalisando] = useState(false);
  const [notas, setNotas] = useState("");
  const [prazo, setPrazo] = useState("");
  const toast = useToast();

  async function load() {
    const j = await api<JobDetail>(`/jobs/${jobId}`);
    setJob(j);
    setNotas(j.card?.notas ?? "");
    setPrazo(j.card?.prazo ?? "");
    if (j.cvs[0] && !cv) setCv(await api<CV>(`/cvs/${j.cvs[0].id}`));
  }

  useEffect(() => {
    load().catch((e) => toast(e.message, "erro"));
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  async function gerarCV() {
    setGerando(true);
    try {
      const g = await api<CV>(`/jobs/${jobId}/tailor-cv`, { method: "POST" });
      setCv(await api<CV>(`/cvs/${g.id}`));
      toast("CV adaptado gerado");
      load();
    } catch (e) {
      toast((e as Error).message, "erro");
    } finally {
      setGerando(false);
    }
  }

  async function reanalisar() {
    setReanalisando(true);
    try {
      setJob(await api<JobDetail>(`/jobs/${jobId}/analyze`, { method: "POST" }));
      onChange();
    } catch (e) {
      toast((e as Error).message, "erro");
    } finally {
      setReanalisando(false);
    }
  }

  async function saveCard(patch: Record<string, unknown>) {
    if (!job?.card) return;
    try {
      await api(`/cards/${job.card.id}`, { method: "PATCH", body: patch });
      onChange();
      if (patch.coluna) load();
    } catch (e) {
      toast((e as Error).message, "erro");
    }
  }

  const a = job?.analise;
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/20" onClick={onClose}>
      <aside onClick={(e) => e.stopPropagation()} className="flex h-full w-full max-w-2xl flex-col overflow-y-auto bg-white shadow-2xl">
        {!job ? (
          <div className="grid flex-1 place-items-center"><Spinner className="h-6 w-6 text-indigo-500" /></div>
        ) : (
          <>
            <div className="sticky top-0 z-10 border-b border-slate-100 bg-white px-6 py-4">
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <h2 className="text-lg font-semibold leading-snug text-slate-900">{job.cargo}</h2>
                  <p className="text-sm text-slate-500">{job.empresa} · {job.local || "local não informado"}</p>
                </div>
                <button onClick={onClose} className="rounded-lg p-1 text-xl leading-none text-slate-400 hover:bg-slate-100">×</button>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                {job.modelo && <Badge tone="indigo">{MODELO[job.modelo] ?? job.modelo}</Badge>}
                <Badge>{salario(job)}</Badge>
                {job.publicada_em && <span>publicada {relTime(job.publicada_em)}</span>}
                <span>· fonte: {job.fonte}</span>
                {/^https?:\/\//.test(job.url) && (
                  <a href={job.url} target="_blank" rel="noreferrer" className="font-medium text-indigo-600 hover:underline">abrir vaga original ↗</a>
                )}
              </div>
              {job.card && (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <select value={job.card.coluna} onChange={(e) => saveCard({ coluna: e.target.value })}
                    className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm">
                    {COLUNAS.map((c) => <option key={c.id} value={c.id}>{c.titulo}</option>)}
                  </select>
                  {job.card.coluna === "desafio" && (
                    <input value={prazo} onChange={(e) => setPrazo(e.target.value)} onBlur={() => saveCard({ prazo })}
                      placeholder="prazo (ex.: 5 dias)" className="w-40 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
                  )}
                </div>
              )}
            </div>

            <div className="space-y-6 px-6 py-5">
              {/* Pré-análise */}
              <section>
                <div className="mb-2 flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-slate-900">Pré-análise da IA</h3>
                  {a && <TagBadge tag={a.tag} score={a.score} />}
                  {a && <Badge tone={a.veredito === "DESCARTADA" ? "red" : a.veredito === "ALERTA" ? "amber" : "green"}>{a.veredito}</Badge>}
                  <button onClick={reanalisar} disabled={reanalisando} className="ml-auto text-xs text-slate-400 hover:text-slate-700">
                    {reanalisando ? "analisando…" : "reanalisar"}
                  </button>
                </div>
                {!a ? (
                  <p className="text-sm text-slate-500">Ainda não analisada.</p>
                ) : (
                  <div className="space-y-3 text-sm">
                    {a.motivos_descarte.length > 0 && <p className="rounded-lg bg-slate-50 px-3 py-2 text-slate-600"><b>Motivo:</b> {a.motivos_descarte.join("; ")}</p>}
                    {a.alertas.length > 0 && (
                      <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900">
                        {a.alertas.map((x, i) => <p key={i}>⚠️ {x}</p>)}
                      </div>
                    )}
                    {a.resumo && <p className="text-slate-600"><b>Problema do empregador:</b> {a.resumo}</p>}
                    {a.motivos.length > 0 && (
                      <ul className="list-disc space-y-0.5 pl-5 text-slate-700">{a.motivos.map((m, i) => <li key={i}>{m}</li>)}</ul>
                    )}
                    {a.requisitos.length > 0 && (
                      <table className="w-full border-collapse text-xs">
                        <thead><tr className="text-left text-slate-500"><th className="py-1 pr-2 font-medium">Requisito</th><th className="py-1 pr-2 font-medium">Evidência</th><th className="py-1 font-medium" /></tr></thead>
                        <tbody>
                          {a.requisitos.map((r, i) => (
                            <tr key={i} className="border-t border-slate-100 align-top">
                              <td className="py-1.5 pr-2">{r.requisito}<div className="text-[10px] text-slate-400">{r.tipo}</div></td>
                              <td className="py-1.5 pr-2 text-slate-600">{r.evidencia || "—"}{r.fatos_ids.length > 0 && <div className="text-[10px] text-slate-400">{r.fatos_ids.join(", ")}</div>}</td>
                              <td className="py-1.5"><Badge tone={CLASS_TONE[r.classificacao]}>{r.classificacao}</Badge></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                    {a.lacunas.length > 0 && (
                      <div><b className="text-slate-700">Lacunas:</b><ul className="list-disc pl-5 text-slate-600">{a.lacunas.map((l, i) => <li key={i}>{l}</li>)}</ul></div>
                    )}
                    <p className="text-[11px] text-slate-400">{a.modelo} · {relTime(a.criado_em)}</p>
                  </div>
                )}
              </section>

              {/* CV adaptado */}
              <section>
                <div className="mb-2 flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-slate-900">CV adaptado</h3>
                  <Button className="ml-auto" onClick={gerarCV} disabled={gerando}>
                    {gerando ? <><Spinner /> Gerando (1 a 3 min)…</> : cv ? "Gerar de novo" : "Gerar CV adaptado"}
                  </Button>
                </div>
                {cv ? (
                  <CVView cv={cv} versoes={job.cvs}
                    onVersao={async (id) => setCv(await api<CV>(`/cvs/${id}`))}
                    onNova={(c) => { setCv(c); load(); }} />
                ) : <p className="text-sm text-slate-500">O CV usa só fatos do seu fatos.yaml. Você baixa em DOCX ou PDF e se candidata.</p>}
              </section>

              {/* Notas e histórico */}
              {job.card && (
                <section>
                  <h3 className="mb-2 text-sm font-semibold text-slate-900">Notas</h3>
                  <textarea value={notas} onChange={(e) => setNotas(e.target.value)} onBlur={() => notas !== job.card?.notas && saveCard({ notas })}
                    rows={3} placeholder="Recrutador, datas, impressões…"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-400" />
                  <h3 className="mb-1 mt-4 text-sm font-semibold text-slate-900">Histórico</h3>
                  <ul className="space-y-0.5 text-xs text-slate-500">
                    {job.historico.map((h, i) => (
                      <li key={i}>{new Date(h.em).toLocaleString("pt-BR")} · {h.de ? `${titulo(h.de)} → ` : ""}{titulo(h.para)} <span className="text-slate-400">({h.autor})</span></li>
                    ))}
                  </ul>
                </section>
              )}

              <section>
                <h3 className="mb-2 text-sm font-semibold text-slate-900">Descrição da vaga</h3>
                <Markdown text={job.descricao || "_Sem descrição._"} className="text-slate-700" />
              </section>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}

const titulo = (id: string) => COLUNAS.find((c) => c.id === id)?.titulo ?? id;

function CVView({ cv, versoes, onVersao, onNova }: {
  cv: CV; versoes: JobDetail["cvs"]; onVersao: (id: number) => void; onNova: (c: CV) => void;
}) {
  const [tab, setTab] = useState<"cv" | "diff" | "relatorio">("cv");
  const toast = useToast();
  return (
    <div className="rounded-xl border border-slate-200">
      <div className="flex flex-wrap items-center gap-1 border-b border-slate-100 px-2 py-1.5">
        {(["cv", "diff", "relatorio"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`rounded-md px-2.5 py-1 text-xs ${tab === t ? "bg-slate-100 font-medium" : "text-slate-500"}`}>
            {t === "cv" ? "CV" : t === "diff" ? "Diff vs. base" : "Relatório"}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-1">
          {versoes.length > 1 && (
            <select value={cv.id} onChange={(e) => onVersao(Number(e.target.value))} title="Versões deste CV"
              className="max-w-48 rounded-md border border-slate-200 bg-white px-1.5 py-1 text-xs">
              {versoes.map((v, i) => (
                <option key={v.id} value={v.id}>
                  v{versoes.length - i} · {!v.nota || v.nota === "gerado" ? "gerado" : `ajuste: ${v.nota.slice(0, 40)}`}
                </option>
              ))}
            </select>
          )}
          <a href={`/api/cvs/${cv.id}/download?format=docx`} className="rounded-md border border-slate-200 px-2.5 py-1 text-xs hover:bg-slate-50">DOCX</a>
          <a href={`/api/cvs/${cv.id}/download?format=pdf`} className="rounded-md border border-slate-200 px-2.5 py-1 text-xs hover:bg-slate-50">PDF</a>
        </div>
      </div>
      {cv.validacao.length > 0 && (
        <div className="border-b border-amber-100 bg-amber-50 px-4 py-2 text-xs text-amber-900">
          O validador removeu {cv.validacao.length} bullet(s) sem fato que sustente: {cv.validacao.map((v) => v.motivo).join("; ")}
        </div>
      )}
      <div className="max-h-[60vh] overflow-y-auto px-4 py-3">
        {tab === "cv" && <Markdown text={cv.cv_md} />}
        {tab === "diff" && <LineDiff base={cv.cv_base_md ?? ""} novo={cv.cv_md} resumo={cv.diff_md} />}
        {tab === "relatorio" && <Markdown text={cv.relatorio_md} />}
      </div>
      {cv.mensagem_recrutador && (
        <div className="border-t border-slate-100 px-4 py-3 text-sm">
          <div className="mb-1 flex items-center text-xs font-medium text-slate-500">
            Mensagem ao recrutador ({cv.mensagem_recrutador.length} caracteres)
            <button className="ml-auto text-indigo-600" onClick={() => { navigator.clipboard.writeText(cv.mensagem_recrutador); toast("Mensagem copiada"); }}>copiar</button>
          </div>
          <p className="text-slate-700">{cv.mensagem_recrutador}</p>
        </div>
      )}
      <AjusteChat cvId={cv.id} onNova={onNova} />
    </div>
  );
}

type AjusteMsg = { role: "user" | "ia"; text: string; mudancas?: string[]; removidos?: number; erro?: boolean };

/** Chat para ajustar só este CV. Cada ajuste vira uma versão nova; as anteriores ficam no seletor. */
function AjusteChat({ cvId, onNova }: { cvId: number; onNova: (c: CV) => void }) {
  const [msgs, setMsgs] = useState<AjusteMsg[]>([]);
  const [texto, setTexto] = useState("");
  const [pensando, setPensando] = useState(false);
  const fim = useRef<HTMLDivElement>(null);

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
      const r = await api<{ resposta: string; mudancas: string[]; validacao: unknown[]; cv: CV | null }>(`/cvs/${cvId}/chat`, {
        method: "POST", body: { mensagem: t, historico },
      });
      if (r.cv) onNova(r.cv);
      setMsgs((m) => [...m, { role: "ia", text: r.cv ? r.resposta : `${r.resposta} (nada mudou)`, mudancas: r.mudancas, removidos: r.validacao.length }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "ia", text: `Não consegui: ${(e as Error).message}`, erro: true }]);
    } finally {
      setPensando(false);
    }
  }

  const atalhos = ["Encurta o resumo para 2 linhas", "Deixa em 1 página", "Sobe o bullet mais ligado à vaga", "Escreve em inglês"];
  return (
    <div className="border-t border-slate-100 bg-slate-50/60 px-4 py-3">
      <div className="mb-2 text-xs font-medium text-slate-600">💬 Ajustar este CV com a IA</div>
      {msgs.length === 0 ? (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {atalhos.map((a) => (
            <button key={a} onClick={() => enviar(a)} disabled={pensando}
              className="rounded-full border border-slate-200 bg-white px-2.5 py-0.5 text-[11px] text-slate-600 hover:border-indigo-300 hover:text-indigo-700">
              {a}
            </button>
          ))}
        </div>
      ) : (
        <div className="mb-2 max-h-56 space-y-1.5 overflow-y-auto pr-1">
          {msgs.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[90%] rounded-xl px-3 py-1.5 text-xs ${m.role === "user" ? "bg-indigo-600 text-white" : m.erro ? "bg-red-50 text-red-700" : "border border-slate-200 bg-white text-slate-700"}`}>
                {m.text}
                {m.mudancas && m.mudancas.length > 0 && (
                  <ul className="mt-1 space-y-0.5 text-slate-500">{m.mudancas.map((x, j) => <li key={j}>✏️ {x}</li>)}</ul>
                )}
                {!!m.removidos && <p className="mt-1 text-amber-700">O validador removeu {m.removidos} bullet(s) sem fato.</p>}
              </div>
            </div>
          ))}
          {pensando && <div className="flex items-center gap-2 text-xs text-slate-500"><Spinner /> ajustando o CV… (até 1 min)</div>}
          <div ref={fim} />
        </div>
      )}
      <div className="flex items-end gap-2">
        <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={1}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(); } }}
          placeholder="Ex.: tira a seção de certificações e destaca o Power BI"
          className="flex-1 resize-none rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs outline-none focus:border-indigo-400" />
        <Button onClick={() => enviar()} disabled={!texto.trim() || pensando} className="py-1 text-xs">
          {pensando ? <Spinner /> : "Ajustar"}
        </Button>
      </div>
      <p className="mt-1 text-[10px] text-slate-400">Cada ajuste vira uma versão nova deste CV; as anteriores continuam no seletor de versões. Nada é inventado: bullet sem fato é removido.</p>
    </div>
  );
}

