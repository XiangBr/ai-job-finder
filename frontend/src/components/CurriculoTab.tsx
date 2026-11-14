import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import CVChat, { type Draft } from "./CVChat";
import { Button, LineDiff, Markdown, Spinner, useToast } from "./ui";

type Modo = "otimizar" | "como_esta";

const MODOS: { id: Modo; titulo: string; desc: string }[] = [
  { id: "otimizar", titulo: "Otimizar com IA", desc: "A IA reescreve o CV base com as boas práticas (título-alvo, bullets com resultado, poda). Onde faltar número, deixa [[...]]." },
  { id: "como_esta", titulo: "Usar como está", desc: "O texto do seu CV vira o CV base sem reescrita, só com títulos e listas marcados. A IA monta apenas o banco de fatos e sugere correções." },
];

interface Preview {
  modo: Modo;
  arquivo: string;
  caracteres: number;
  texto_extraido: string;
  modelo: string;
  nome: string;
  fatos_yaml: string;
  cv_base_md: string;
  correcoes: string[];
  pontos_fortes: string[];
  perguntas: string[];
}
interface Profile { nome: string; fatos_yaml: string; cv_base_md: string; regras_cv: string }

const ACCEPT = ".pdf,.docx,.doc,.odt,.rtf";

export default function CurriculoTab({ onSaved }: { onSaved: () => void }) {
  const [p, setP] = useState<Profile | null>(null);
  const [original, setOriginal] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<string | null>(null);
  const [erro, setErro] = useState("");
  const [prev, setPrev] = useState<Preview | null>(null);
  const [drag, setDrag] = useState(false);
  const [modo, setModo] = useState<"ver" | "diff" | "fatos" | "editar">("ver");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [rascunho, setRascunho] = useState("");
  const [regras, setRegras] = useState("");
  const [modoEnvio, setModoEnvio] = useState<Modo>(() => {
    try { return (localStorage.getItem("acv-modo-cv") as Modo) || "otimizar"; } catch { return "otimizar"; }
  });
  const [salvando, setSalvando] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const toast = useToast();

  async function load() {
    const d = await api<Profile>("/profile");
    setP(d);
    setRascunho(d.cv_base_md);
    setRegras(d.regras_cv ?? "");
    const o = await api<{ nome: string | null }>("/profile/cv-original/info");
    setOriginal(o.nome);
  }
  useEffect(() => { load(); }, []);

  async function enviar(file: File) {
    setErro("");
    setPrev(null);
    setEnviando(file.name);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("modo", modoEnvio);
    try {
      const res = await fetch("/api/profile/cv-upload", { method: "POST", body: fd, credentials: "same-origin" });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) throw new ApiError(res.status, typeof d.detail === "string" ? d.detail : "falha no envio");
      setPrev(d as Preview);
      setOriginal(file.name);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setEnviando(null);
      if (input.current) input.current.value = "";
    }
  }

  async function salvarDraft() {
    if (!draft) return;
    setSalvando(true);
    try {
      const d = await api<Profile>("/profile", { method: "PUT", body: draft });
      setP(d);
      setRascunho(d.cv_base_md);
      setRegras(d.regras_cv ?? "");
      setDraft(null);
      setModo("ver");
      toast("Fatos e CV base salvos");
      onSaved();
    } catch (e) {
      toast((e as Error).message, "erro");
    } finally {
      setSalvando(false);
    }
  }

  async function salvarRegras() {
    setSalvando(true);
    try {
      const d = await api<Profile>("/profile", { method: "PUT", body: { regras_cv: regras } });
      setP(d);
      toast("Regras salvas. Valem para os próximos CVs adaptados");
      onSaved();
    } catch (e) {
      toast((e as Error).message, "erro");
    } finally {
      setSalvando(false);
    }
  }

  async function salvarCV(texto: string) {
    setSalvando(true);
    try {
      setP(await api<Profile>("/profile", { method: "PUT", body: { cv_base_md: texto } }));
      setModo("ver");
      toast("CV base salvo");
      onSaved();
    } catch (e) {
      toast((e as Error).message, "erro");
    } finally {
      setSalvando(false);
    }
  }

  if (!p) return <div className="grid h-64 place-items-center"><Spinner className="h-6 w-6 text-indigo-500" /></div>;

  return (
    <div className="space-y-4">
      {/* ------------------------------------------------ upload */}
      <section
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) enviar(f); }}
        className={`rounded-2xl border-2 border-dashed p-6 text-center transition ${drag ? "border-indigo-400 bg-indigo-50" : "border-slate-300 bg-white"}`}
      >
        {enviando ? (
          <div className="flex flex-col items-center gap-2 py-4 text-sm text-slate-600">
            <Spinner className="h-6 w-6 text-indigo-500" />
            <b>Lendo {enviando}</b>
            <span className="text-xs text-slate-500">
              {modoEnvio === "otimizar" ? "A IA está montando o banco de fatos e reescrevendo o CV base." : "A IA está montando o banco de fatos. Seu texto não será alterado."} Leva de 1 a 3 minutos.
            </span>
          </div>
        ) : (
          <>
            <div className="text-3xl">📄</div>
            <h3 className="mt-1 text-sm font-semibold text-slate-900">Envie seu currículo</h3>
            <p className="mx-auto mt-1 max-w-md text-xs text-slate-500">
              PDF, DOCX ou DOC (Word). Nada muda no seu perfil até você revisar e salvar.
            </p>
            <div className="mx-auto mt-4 grid max-w-xl gap-2 text-left sm:grid-cols-2">
              {MODOS.map((m) => (
                <label key={m.id} className={`cursor-pointer rounded-xl border p-3 transition ${modoEnvio === m.id ? "border-indigo-400 bg-indigo-50/60 ring-1 ring-indigo-200" : "border-slate-200 hover:border-slate-300"}`}>
                  <span className="flex items-center gap-2 text-sm font-medium text-slate-800">
                    <input type="radio" name="modo-cv" checked={modoEnvio === m.id}
                      onChange={() => { setModoEnvio(m.id); try { localStorage.setItem("acv-modo-cv", m.id); } catch { /* sem storage */ } }} />
                    {m.titulo}
                  </span>
                  <span className="mt-1 block text-[11px] leading-snug text-slate-500">{m.desc}</span>
                </label>
              ))}
            </div>
            <div className="mt-3 flex items-center justify-center gap-3">
              <Button onClick={() => input.current?.click()}>Escolher arquivo</Button>
              <span className="text-xs text-slate-400">ou arraste para cá</span>
            </div>
            {original && (
              <p className="mt-3 text-xs text-slate-500">
                Último enviado: <a href="/api/profile/cv-original" className="text-indigo-600 hover:underline">{original}</a>
              </p>
            )}
          </>
        )}
        <input ref={input} type="file" accept={ACCEPT} className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) enviar(f); }} />
        {erro && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-left text-sm text-red-700">{erro}</p>}
      </section>

      {prev && <PreviewCard prev={prev} temFatos={!!p.fatos_yaml.trim()} temCV={!!p.cv_base_md.trim()}
        onCancel={() => setPrev(null)} onApplied={() => { setPrev(null); load(); onSaved(); }} />}

      {/* ------------------------------------------------ chat */}
      <CVChat
        atual={draft ?? { fatos_yaml: p.fatos_yaml, cv_base_md: p.cv_base_md, regras_cv: p.regras_cv ?? "" }}
        onDraft={(d) => {
          setDraft(d);
          setModo(d.cv_base_md !== p.cv_base_md ? "diff" : d.fatos_yaml !== p.fatos_yaml ? "fatos" : "ver");
        }}
      />

      {/* ------------------------------------------------ regras */}
      <RegrasCard salvas={p.regras_cv ?? ""} rascunhoIA={draft && draft.regras_cv !== (p.regras_cv ?? "") ? draft.regras_cv : null}
        valor={regras} onChange={setRegras} onSalvar={salvarRegras} salvando={salvando} />

      {/* ------------------------------------------------ CV base */}
      <section className={`rounded-2xl border bg-white ${draft ? "border-amber-300 ring-2 ring-amber-100" : "border-slate-200"}`}>
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-4 py-3">
          <h3 className="text-sm font-semibold text-slate-900">CV base</h3>
          {draft
            ? <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-medium text-amber-800">alterações da IA não salvas</span>
            : <span className="text-xs text-slate-500">ponto de partida de todo CV adaptado</span>}
          <div className="ml-auto flex gap-1">
            {([["ver", "Visualizar"], ...(draft ? [["diff", "Diferenças no CV"], ["fatos", "Diferenças nos fatos"]] : []), ...(!draft ? [["editar", "Editar"]] : [])] as [typeof modo, string][]).map(([k, label]) => (
              <button key={k} onClick={() => setModo(k)} className={`rounded-md px-2.5 py-1 text-xs ${modo === k ? "bg-slate-100 font-medium" : "text-slate-500"}`}>{label}</button>
            ))}
          </div>
        </div>
        {modo === "ver" && (
          <div className="px-6 py-4">
            {(draft?.cv_base_md ?? p.cv_base_md).trim()
              ? <Markdown text={draft?.cv_base_md ?? p.cv_base_md} />
              : <p className="text-sm text-slate-500">Nenhum CV base ainda. Envie seu currículo acima.</p>}
          </div>
        )}
        {modo === "diff" && draft && (
          <div className="max-h-[60vh] overflow-y-auto px-6 py-4">
            {draft.cv_base_md === p.cv_base_md ? <p className="text-sm text-slate-500">O CV base não mudou.</p> : <LineDiff base={p.cv_base_md} novo={draft.cv_base_md} />}
          </div>
        )}
        {modo === "fatos" && draft && (
          <div className="max-h-[60vh] overflow-y-auto px-6 py-4">
            {draft.fatos_yaml === p.fatos_yaml ? <p className="text-sm text-slate-500">O banco de fatos não mudou.</p> : <LineDiff base={p.fatos_yaml} novo={draft.fatos_yaml} />}
          </div>
        )}
        {modo === "editar" && !draft && (
          <div className="p-3">
            <textarea value={rascunho} onChange={(e) => setRascunho(e.target.value)} spellCheck={false} rows={28}
              className="w-full resize-y rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-xs leading-relaxed outline-none focus:border-indigo-300" />
            <p className="mb-2 text-[11px] text-slate-400">Markdown: "# Nome", "## Seção", "### Cargo | Empresa | período", bullets com "- ". Trechos entre [[ ]] marcam números que faltam.</p>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => { setRascunho(p.cv_base_md); setModo("ver"); }}>Cancelar</Button>
              <Button onClick={() => salvarCV(rascunho)} disabled={salvando || rascunho === p.cv_base_md}>{salvando ? "Salvando…" : "Salvar CV base"}</Button>
            </div>
          </div>
        )}
      </section>

      {draft && (
        <div className="sticky bottom-4 z-10 flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white/95 px-4 py-3 shadow-lg backdrop-blur">
          <span className="text-sm text-slate-600">
            A IA alterou {[draft.cv_base_md !== p.cv_base_md && "o CV base", draft.fatos_yaml !== p.fatos_yaml && "o banco de fatos", draft.regras_cv !== (p.regras_cv ?? "") && "as suas regras"].filter(Boolean).join(", ")}. Confira e salve.
          </span>
          <Button variant="ghost" className="ml-auto" onClick={() => { setDraft(null); setModo("ver"); }}>Descartar</Button>
          <Button onClick={salvarDraft} disabled={salvando}>{salvando ? "Salvando…" : "Salvar alterações"}</Button>
        </div>
      )}
    </div>
  );
}

function RegrasCard({ salvas, rascunhoIA, valor, onChange, onSalvar, salvando }: {
  salvas: string; rascunhoIA: string | null; valor: string; onChange: (v: string) => void; onSalvar: () => void; salvando: boolean;
}) {
  return (
    <section className={`rounded-2xl border bg-white p-5 ${rascunhoIA !== null ? "border-amber-300 ring-2 ring-amber-100" : "border-slate-200"}`}>
      <div className="flex items-start gap-2">
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-slate-900">📝 Minhas regras para o CV</h3>
          <p className="mt-0.5 text-xs text-slate-500">
            Como você quer que os CVs adaptados sejam escritos. Elas têm prioridade sobre as boas práticas padrão
            (fórmula XYZ, resumo, ordem das seções), mas não liberam inventar nada: todo bullet continua precisando de um fato.
          </p>
        </div>
        {rascunhoIA !== null && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-medium text-amber-800">alterado pela IA</span>}
      </div>
      {rascunhoIA !== null ? (
        <pre className="mt-3 whitespace-pre-wrap rounded-lg bg-amber-50/60 p-3 text-sm text-slate-700">{rascunhoIA || "(sem regras)"}</pre>
      ) : (
        <>
          <textarea value={valor} onChange={(e) => onChange(e.target.value)} rows={4}
            placeholder={"- Não usar a fórmula XYZ: bullets curtos, só ação e ferramenta\n- Resumo com no máximo 2 linhas\n- Sempre 1 página"}
            className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-400" />
          <div className="mt-2 flex items-center justify-end gap-2">
            {valor !== salvas && <span className="text-xs text-slate-400">não salvo</span>}
            <Button onClick={onSalvar} disabled={salvando || valor === salvas}>{salvando ? "Salvando…" : "Salvar regras"}</Button>
          </div>
        </>
      )}
    </section>
  );
}

function PreviewCard({ prev, temFatos, temCV, onCancel, onApplied }: {
  prev: Preview; temFatos: boolean; temCV: boolean; onCancel: () => void; onApplied: () => void;
}) {
  const semIA = prev.modelo === "mock" || !prev.fatos_yaml.trim();
  const [tab, setTab] = useState<"cv" | "diag" | "fatos" | "texto">(semIA || prev.modo === "como_esta" ? "cv" : "diag");
  const [usarCV, setUsarCV] = useState(true);
  const [usarFatos, setUsarFatos] = useState(!semIA);
  const [salvando, setSalvando] = useState(false);
  const toast = useToast();

  async function aplicar() {
    const body: Record<string, string> = {};
    if (usarCV) body.cv_base_md = prev.cv_base_md;
    if (usarFatos && prev.fatos_yaml.trim()) body.fatos_yaml = prev.fatos_yaml;
    if (prev.nome && usarFatos) body.nome = prev.nome;
    if (!Object.keys(body).length) return onCancel();
    setSalvando(true);
    try {
      await api("/profile", { method: "PUT", body });
      toast("Perfil atualizado com o novo currículo");
      onApplied();
    } catch (e) {
      toast((e as Error).message, "erro");
    } finally {
      setSalvando(false);
    }
  }

  const comoEsta = prev.modo === "como_esta";
  const tabs: [typeof tab, string][] = comoEsta
    ? [["cv", "CV base (seu texto)"], ["fatos", "Banco de fatos"], ["diag", "Sugestões"]]
    : [["diag", "Diagnóstico"], ["cv", "CV base sugerido"], ["fatos", "Banco de fatos"], ["texto", "Texto extraído"]];
  return (
    <section className="rounded-2xl border border-indigo-200 bg-white">
      <div className="border-b border-slate-100 px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-900">Prévia: {prev.arquivo}</h3>
        <p className="text-xs text-slate-500">
          {comoEsta ? "Usar como está · " : "Otimizado com IA · "}{prev.caracteres.toLocaleString("pt-BR")} caracteres lidos · {prev.modelo}
        </p>
        {comoEsta && (
          <p className="mt-1 text-xs text-slate-500">O texto é o do seu arquivo, na ordem em que ele foi lido. Ajuste títulos ou ordem em "Editar" depois de salvar, se precisar.</p>
        )}
      </div>
      <div className="flex flex-wrap gap-1 border-b border-slate-100 px-3 py-1.5">
        {tabs.filter(([k]) => !(semIA && (k === "diag" || k === "fatos"))).map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)} className={`rounded-md px-2.5 py-1 text-xs ${tab === k ? "bg-slate-100 font-medium" : "text-slate-500"}`}>{label}</button>
        ))}
      </div>
      <div className="max-h-[55vh] overflow-y-auto px-5 py-4 text-sm">
        {tab === "diag" && (
          <div className="space-y-4">
            {comoEsta && <p className="text-xs text-slate-500">Seu CV não foi alterado. Estas são só sugestões, caso queira aplicar à mão (ou reenviar escolhendo "Otimizar com IA").</p>}
            <Lista titulo="Correções de maior impacto" itens={prev.correcoes} numerada />
            <Lista titulo="O que já está forte" itens={prev.pontos_fortes} />
            <Lista titulo="Perguntas para completar os números" itens={prev.perguntas}
              rodape="Responda editando o banco de fatos ou o CV base depois de salvar. Os trechos [[...]] no CV marcam onde entra cada resposta." />
          </div>
        )}
        {tab === "cv" && <Markdown text={prev.cv_base_md} />}
        {tab === "fatos" && <pre className="whitespace-pre-wrap font-mono text-xs text-slate-700">{prev.fatos_yaml}</pre>}
        {tab === "texto" && <pre className="whitespace-pre-wrap font-mono text-xs text-slate-600">{prev.texto_extraido}</pre>}
      </div>
      <div className="space-y-2 border-t border-slate-100 px-4 py-3">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={usarCV} onChange={(e) => setUsarCV(e.target.checked)} />
          {temCV ? "Substituir o CV base atual" : "Usar como CV base"}
        </label>
        {!semIA && (
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-1" checked={usarFatos} onChange={(e) => setUsarFatos(e.target.checked)} />
            <span>
              {temFatos ? "Substituir o banco de fatos atual" : "Usar como banco de fatos"}
              {temFatos && usarFatos && <span className="block text-xs text-amber-700">Números e confirmações que você já adicionou ao banco atual serão perdidos.</span>}
              {!usarFatos && usarCV && <span className="block text-xs text-amber-700">O CV novo aponta para fatos novos. Sem trocar o banco de fatos, o validador pode cortar bullets nos CVs adaptados.</span>}
            </span>
          </label>
        )}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onCancel}>Descartar</Button>
          <Button onClick={aplicar} disabled={salvando || (!usarCV && !usarFatos)}>{salvando ? "Salvando…" : "Salvar no perfil"}</Button>
        </div>
      </div>
    </section>
  );
}

function Lista({ titulo, itens, numerada, rodape }: { titulo: string; itens: string[]; numerada?: boolean; rodape?: string }) {
  if (!itens.length) return null;
  const Tag = numerada ? "ol" : "ul";
  return (
    <div>
      <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{titulo}</h4>
      <Tag className={`${numerada ? "list-decimal" : "list-disc"} space-y-1 pl-5 text-slate-700`}>
        {itens.map((x, i) => <li key={i}>{x.replace(/^\s*\d+[.)]\s*/, "")}</li>)}
      </Tag>
      {rodape && <p className="mt-1 text-xs text-slate-400">{rodape}</p>}
    </div>
  );
}
