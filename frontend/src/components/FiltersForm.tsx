import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { ChipsInput, Field, NumberInput, Section, Toggle } from "./fields";
import { Button, Spinner, useToast } from "./ui";

interface Cargo { area: string; prioridade: number; titulos: string[] }
interface Local { aceita: boolean; prioridade: number; cidades: string[] }
export interface Filtros {
  cargos: Cargo[];
  excluir_titulos: string[];
  nivel: string[];
  contrato: string[];
  modelo_trabalho: { remoto: { aceita: boolean; prioridade: number; abrangencia: string }; hibrido: Local; presencial: Local };
  raio_km: number | null;
  aceita_mudanca: boolean;
  remuneracao: { estagio_minimo_bolsa: number | null; clt_minimo_base: number | null; clt_exige: string[]; pj_minimo: number | null; nao_informado: "marcar" | "descartar" };
  empresas_alvo: string[];
  empresas_bloqueadas: string[];
  setores_preferidos: string[];
  setores_evitar: string[];
  idiomas_vaga: string[];
  ingles_maximo_exigido: string;
  restricoes: { disponibilidade_estagio_max_meses: number | null; anos_experiencia_max: number | null; exige_formado: boolean };
  palavras_excluir: string[];
  publicada_ha_no_maximo_dias: number;
  fontes: string[];
  score_minimo_para_alerta: number;
  filtrar_titulo_fora_da_area: boolean;
  observacoes: string;
}
type Key = keyof Filtros;
type Msg = { role: "user" | "ia"; text: string; perguntas?: string[] };

const GROUPS: Record<string, Key[]> = {
  cargos: ["cargos"],
  nivel: ["nivel", "contrato", "excluir_titulos"],
  onde: ["modelo_trabalho", "raio_km", "aceita_mudanca"],
  salario: ["remuneracao"],
  restricoes: ["restricoes", "ingles_maximo_exigido", "idiomas_vaga"],
  empresas: ["empresas_alvo", "empresas_bloqueadas", "setores_preferidos", "setores_evitar"],
  busca: ["palavras_excluir", "publicada_ha_no_maximo_dias", "fontes", "score_minimo_para_alerta", "filtrar_titulo_fora_da_area"],
  obs: ["observacoes"],
};

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

export default function FiltersForm({ onSaved }: { onSaved: () => void }) {
  const [saved, setSaved] = useState<Filtros | null>(null);
  const [f, setF] = useState<Filtros | null>(null);
  const [aiKeys, setAiKeys] = useState<Set<Key>>(new Set());
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [texto, setTexto] = useState("");
  const [pensando, setPensando] = useState(false);
  const [salvando, setSalvando] = useState(false);
  const toast = useToast();
  const chatEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<Filtros>("/filters/form").then((d) => { const n = norm(d); setSaved(n); setF(n); });
  }, []);
  useEffect(() => {
    chatEnd.current?.scrollIntoView({ block: "nearest" });
  }, [msgs, pensando]);

  if (!f || !saved) return <div className="grid h-64 place-items-center"><Spinner className="h-6 w-6 text-indigo-500" /></div>;

  const set = <K extends Key>(k: K, v: Filtros[K]) => setF({ ...f, [k]: v });
  const dirty = !same(f, saved);
  const changed = (g: string) => GROUPS[g].some((k) => aiKeys.has(k));

  async function enviar() {
    const t = texto.trim();
    if (!t || pensando || !f) return;
    const historico = msgs.map((m) => ({ role: m.role === "ia" ? "assistant" : "user", text: m.text }));
    setMsgs((m) => [...m, { role: "user", text: t }]);
    setTexto("");
    setPensando(true);
    try {
      const r = await api<{ filtros: Filtros; resumo: string; perguntas: string[] }>("/filters/ai-fill", {
        method: "POST", body: { texto: t, form: f, historico },
      });
      const nf = norm(r.filtros);
      const novos = (Object.keys(nf) as Key[]).filter((k) => !same(nf[k], f[k]));
      setF(nf);
      setAiKeys((s) => new Set([...s, ...novos]));
      setMsgs((m) => [...m, { role: "ia", text: novos.length ? r.resumo : "Não encontrei nada para mudar. Pode detalhar?", perguntas: r.perguntas }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "ia", text: `Não consegui preencher: ${(e as Error).message}` }]);
    } finally {
      setPensando(false);
    }
  }

  async function salvar() {
    if (!f) return;
    setSalvando(true);
    try {
      const d = norm(await api<Filtros>("/filters/form", { method: "PUT", body: norm(f) }));
      setSaved(d);
      setF(d);
      setAiKeys(new Set());
      toast("Filtros salvos. Valem a partir da próxima busca");
      onSaved();
    } catch (e) {
      toast((e as Error).message, "erro");
    } finally {
      setSalvando(false);
    }
  }

  function descartar() {
    setF(saved);
    setAiKeys(new Set());
  }

  const mt = f.modelo_trabalho;
  const rem = f.remuneracao;
  const res = f.restricoes;

  return (
    <div className="space-y-4 pb-24">
      {/* ------------------------------------------------ chat com a IA */}
      <section className="rounded-2xl border border-indigo-200 bg-gradient-to-b from-indigo-50/70 to-white p-5">
        <div className="mb-3">
          <h3 className="text-sm font-semibold text-slate-900">✨ Conte o que você procura</h3>
          <p className="mt-0.5 text-xs text-slate-500">
            Escreva do seu jeito. A IA preenche os campos abaixo, e nada é salvo até você revisar e clicar em Salvar.
          </p>
        </div>
        {msgs.length > 0 && (
          <div className="mb-3 max-h-64 space-y-2 overflow-y-auto pr-1">
            {msgs.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm ${m.role === "user" ? "bg-indigo-600 text-white" : "border border-slate-200 bg-white text-slate-700"}`}>
                  {m.text}
                  {m.perguntas && m.perguntas.length > 0 && (
                    <ul className="mt-1.5 space-y-0.5 border-t border-slate-100 pt-1.5 text-xs text-slate-500">
                      {m.perguntas.map((p, j) => <li key={j}>❓ {p}</li>)}
                    </ul>
                  )}
                </div>
              </div>
            ))}
            {pensando && (
              <div className="flex"><div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3.5 py-2 text-sm text-slate-500"><Spinner /> preenchendo os campos…</div></div>
            )}
            <div ref={chatEnd} />
          </div>
        )}
        <div className="flex items-end gap-2">
          <textarea
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(); } }}
            rows={msgs.length ? 2 : 3}
            placeholder="Ex.: Quero estágio ou vaga júnior em dados, de preferência remoto. Híbrido só em Curitiba. Bolsa a partir de R$ 2.500. Nada de banco nem varejo; prefiro empresa de tecnologia com time de dados."
            className="flex-1 resize-none rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-400"
          />
          <Button onClick={enviar} disabled={!texto.trim() || pensando} className="h-10">
            {pensando ? <Spinner /> : "Preencher"}
          </Button>
        </div>
      </section>

      {/* ------------------------------------------------ cargos */}
      <Section title="Cargos e áreas" desc="Cada título vira uma busca no LinkedIn e no Indeed. A prioridade define a ordem do rodízio." changed={changed("cargos")}>
        <div className="space-y-3">
          {f.cargos.map((c, i) => (
            <div key={i} className="rounded-xl border border-slate-200 p-3">
              <div className="mb-2 flex items-center gap-2">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">{i + 1}</span>
                <input value={c.area} placeholder="Nome da área (ex.: Ciência de Dados)"
                  onChange={(e) => set("cargos", f.cargos.map((x, j) => (j === i ? { ...x, area: e.target.value } : x)))}
                  className="flex-1 rounded-md border border-transparent px-1.5 py-0.5 text-sm font-medium outline-none hover:border-slate-200 focus:border-indigo-400" />
                <button type="button" title="Subir" disabled={i === 0} onClick={() => set("cargos", move(f.cargos, i, i - 1))} className="px-1 text-slate-400 hover:text-slate-700 disabled:opacity-30">↑</button>
                <button type="button" title="Descer" disabled={i === f.cargos.length - 1} onClick={() => set("cargos", move(f.cargos, i, i + 1))} className="px-1 text-slate-400 hover:text-slate-700 disabled:opacity-30">↓</button>
                <button type="button" title="Remover área" onClick={() => set("cargos", renumber(f.cargos.filter((_, j) => j !== i)))} className="px-1 text-slate-400 hover:text-red-600">×</button>
              </div>
              <ChipsInput value={c.titulos} placeholder="Títulos de busca: digite e Enter"
                onChange={(v) => set("cargos", f.cargos.map((x, j) => (j === i ? { ...x, titulos: v } : x)))} tone="indigo" />
            </div>
          ))}
          <Button variant="outline" onClick={() => set("cargos", [...f.cargos, { area: "", prioridade: f.cargos.length + 1, titulos: [] }])}>+ Adicionar área</Button>
        </div>
      </Section>

      {/* ------------------------------------------------ nível */}
      <Section title="Nível e contrato" changed={changed("nivel")}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Níveis aceitos"><ChipsInput value={f.nivel} onChange={(v) => set("nivel", v)} suggestions={["estagio", "trainee", "junior", "analista", "pleno"]} /></Field>
          <Field label="Tipos de contrato"><ChipsInput value={f.contrato} onChange={(v) => set("contrato", v)} suggestions={["estagio", "clt", "pj"]} /></Field>
          <Field label="Excluir vagas com estas palavras no título" hint="Ex.: Sênior, Pleno, Lead. Vagas com PL, III e IV já saem quando o perfil não busca pleno/sênior." className="sm:col-span-2">
            <ChipsInput value={f.excluir_titulos} onChange={(v) => set("excluir_titulos", v)} tone="red" />
          </Field>
        </div>
      </Section>

      {/* ------------------------------------------------ onde */}
      <Section title="Onde trabalhar" changed={changed("onde")}>
        <div className="space-y-3">
          <div className="grid items-start gap-3 rounded-xl border border-slate-200 p-3 sm:grid-cols-[140px_1fr]">
            <Toggle checked={mt.remoto.aceita} label="Remoto" onChange={(v) => set("modelo_trabalho", { ...mt, remoto: { ...mt.remoto, aceita: v } })} />
            <Field label="Abrangência">
              <input value={mt.remoto.abrangencia} disabled={!mt.remoto.aceita} onChange={(e) => set("modelo_trabalho", { ...mt, remoto: { ...mt.remoto, abrangencia: e.target.value } })}
                className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm outline-none focus:border-indigo-400 disabled:bg-slate-50" placeholder="Brasil" />
            </Field>
          </div>
          {(["hibrido", "presencial"] as const).map((k) => (
            <div key={k} className="grid items-start gap-3 rounded-xl border border-slate-200 p-3 sm:grid-cols-[140px_1fr]">
              <Toggle checked={mt[k].aceita} label={k === "hibrido" ? "Híbrido" : "Presencial"} onChange={(v) => set("modelo_trabalho", { ...mt, [k]: { ...mt[k], aceita: v } })} />
              <Field label="Cidades" hint='Formato "Cidade - UF". Cada cidade vira um local de busca.'>
                <ChipsInput value={mt[k].cidades} onChange={(v) => set("modelo_trabalho", { ...mt, [k]: { ...mt[k], cidades: v } })} placeholder="Curitiba - PR" />
              </Field>
            </div>
          ))}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Raio a partir da cidade"><NumberInput value={f.raio_km} onChange={(v) => set("raio_km", v)} suffix="km" placeholder="só a cidade" /></Field>
            <div className="flex items-end pb-1.5"><Toggle checked={f.aceita_mudanca} onChange={(v) => set("aceita_mudanca", v)} label="Aceita mudar de cidade" /></div>
          </div>
        </div>
      </Section>

      {/* ------------------------------------------------ salário */}
      <Section title="Remuneração mínima" desc="Valores por mês. Vaga abaixo do mínimo é descartada." changed={changed("salario")}>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Bolsa de estágio"><NumberInput prefix="R$" value={rem.estagio_minimo_bolsa} onChange={(v) => set("remuneracao", { ...rem, estagio_minimo_bolsa: v })} /></Field>
          <Field label="Salário base CLT"><NumberInput prefix="R$" value={rem.clt_minimo_base} onChange={(v) => set("remuneracao", { ...rem, clt_minimo_base: v })} /></Field>
          <Field label="PJ"><NumberInput prefix="R$" value={rem.pj_minimo} onChange={(v) => set("remuneracao", { ...rem, pj_minimo: v })} /></Field>
          <Field label="Benefícios obrigatórios (CLT)" className="sm:col-span-2"><ChipsInput value={rem.clt_exige} onChange={(v) => set("remuneracao", { ...rem, clt_exige: v })} suggestions={["VR", "VT", "Plano de saúde"]} /></Field>
          <Field label="Vaga sem salário informado">
            <select value={rem.nao_informado} onChange={(e) => set("remuneracao", { ...rem, nao_informado: e.target.value as "marcar" | "descartar" })}
              className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm">
              <option value="marcar">Manter e marcar "a confirmar"</option>
              <option value="descartar">Descartar</option>
            </select>
          </Field>
        </div>
      </Section>

      {/* ------------------------------------------------ restrições */}
      <Section title="Restrições e idioma" desc="Quando a vaga passa desses limites, ela fica em Selecionadas com o badge de alerta para você decidir." changed={changed("restricoes")}>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Disponibilidade máxima p/ estágio" hint="Meses até a formatura"><NumberInput suffix="meses" value={res.disponibilidade_estagio_max_meses} onChange={(v) => set("restricoes", { ...res, disponibilidade_estagio_max_meses: v })} /></Field>
          <Field label="Anos de experiência (máximo que você tem)"><NumberInput suffix="anos" value={res.anos_experiencia_max} onChange={(v) => set("restricoes", { ...res, anos_experiencia_max: v })} /></Field>
          <div className="flex items-end pb-1.5"><Toggle checked={res.exige_formado} onChange={(v) => set("restricoes", { ...res, exige_formado: v })} label="Já sou formada(o)" /></div>
          <Field label="Inglês: nível máximo que a vaga pode exigir">
            <input list="ingles-opts" value={f.ingles_maximo_exigido} onChange={(e) => set("ingles_maximo_exigido", e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm outline-none focus:border-indigo-400" placeholder="intermediário" />
            <datalist id="ingles-opts">{["básico", "intermediário", "avançado", "fluente"].map((o) => <option key={o} value={o} />)}</datalist>
          </Field>
          <Field label="Idiomas da vaga" className="sm:col-span-2"><ChipsInput value={f.idiomas_vaga} onChange={(v) => set("idiomas_vaga", v)} suggestions={["pt", "en", "es"]} /></Field>
        </div>
      </Section>

      {/* ------------------------------------------------ empresas */}
      <Section title="Empresas e setores" changed={changed("empresas")}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Empresas-alvo" hint="Ganham peso na análise"><ChipsInput value={f.empresas_alvo} onChange={(v) => set("empresas_alvo", v)} tone="green" /></Field>
          <Field label="Empresas bloqueadas" hint="Descartadas sempre (ex.: empresa atual, se a busca for sigilosa)"><ChipsInput value={f.empresas_bloqueadas} onChange={(v) => set("empresas_bloqueadas", v)} tone="red" /></Field>
          <Field label="Setores preferidos"><ChipsInput value={f.setores_preferidos} onChange={(v) => set("setores_preferidos", v)} tone="green" /></Field>
          <Field label="Setores a evitar"><ChipsInput value={f.setores_evitar} onChange={(v) => set("setores_evitar", v)} tone="red" /></Field>
        </div>
      </Section>

      {/* ------------------------------------------------ busca */}
      <Section title="Busca e alertas" changed={changed("busca")}>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Publicada há no máximo"><NumberInput suffix="dias" min={1} value={f.publicada_ha_no_maximo_dias} onChange={(v) => set("publicada_ha_no_maximo_dias", v ?? 7)} /></Field>
          <Field label="Score mínimo para alerta"><NumberInput min={0} value={f.score_minimo_para_alerta} onChange={(v) => set("score_minimo_para_alerta", v ?? 65)} suffix="/ 100" /></Field>
          <Field label="Fontes" hint="Gupy: use + Vaga manual"><ChipsInput value={f.fontes} onChange={(v) => set("fontes", v)} suggestions={["linkedin", "indeed", "glassdoor", "google"]} /></Field>
          <Field label="Descartar se a vaga contiver" hint='Título ou descrição. Ex.: "banco de talentos"' className="sm:col-span-3"><ChipsInput value={f.palavras_excluir} onChange={(v) => set("palavras_excluir", v)} tone="red" /></Field>
          <div className="sm:col-span-3">
            <Toggle checked={f.filtrar_titulo_fora_da_area} onChange={(v) => set("filtrar_titulo_fora_da_area", v)} label="Descartar vagas cujo título não tem nenhuma palavra das suas áreas" />
            <p className="mt-1 text-[11px] text-slate-400">O LinkedIn devolve resultados soltos (ex.: "Auxiliar de Operações TV" numa busca por dados). Isso corta essas vagas antes de gastar IA. Vagas adicionadas à mão nunca são cortadas.</p>
          </div>
        </div>
      </Section>

      {/* ------------------------------------------------ observações */}
      <Section title="Observações em texto livre" desc="O que não cabe nos campos: tipo de time, cultura, horário, propósito. A IA leva isso em conta ao dar o score." changed={changed("obs")}>
        <textarea value={f.observacoes} onChange={(e) => set("observacoes", e.target.value)} rows={4}
          placeholder="Ex.: prefiro empresas com time de dados já estruturado e mentoria; evito vagas com plantão no fim de semana."
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-400" />
      </Section>

      {/* ------------------------------------------------ barra de salvar */}
      {dirty && (
        <div className="sticky bottom-4 z-10 flex items-center gap-3 rounded-2xl border border-slate-200 bg-white/95 px-4 py-3 shadow-lg backdrop-blur">
          <span className="text-sm text-slate-600">Alterações não salvas{aiKeys.size > 0 && " · revise os campos marcados pela IA"}</span>
          <Button variant="ghost" className="ml-auto" onClick={descartar}>Descartar</Button>
          <Button onClick={salvar} disabled={salvando}>{salvando ? "Salvando…" : "Salvar filtros"}</Button>
        </div>
      )}
    </div>
  );
}

function norm(f: Filtros): Filtros {
  return { ...f, cargos: renumber([...f.cargos].sort((a, b) => a.prioridade - b.prioridade)) };
}

function renumber(c: Cargo[]): Cargo[] {
  return c.map((x, i) => ({ ...x, prioridade: i + 1 }));
}

function move(c: Cargo[], from: number, to: number): Cargo[] {
  const a = [...c];
  const [x] = a.splice(from, 1);
  a.splice(to, 0, x);
  return renumber(a);
}
