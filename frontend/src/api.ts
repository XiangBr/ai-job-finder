export type Coluna = "selecionadas" | "candidatura" | "entrevista" | "desafio" | "aprovado" | "descartadas";

export const COLUNAS: { id: Coluna; titulo: string; cor: string }[] = [
  { id: "selecionadas", titulo: "Selecionadas", cor: "bg-indigo-500" },
  { id: "candidatura", titulo: "Candidatura enviada", cor: "bg-sky-500" },
  { id: "entrevista", titulo: "Entrevista", cor: "bg-teal-500" },
  { id: "desafio", titulo: "Desafio", cor: "bg-amber-500" },
  { id: "aprovado", titulo: "Aprovado", cor: "bg-green-500" },
  { id: "descartadas", titulo: "Descartadas", cor: "bg-slate-400" },
];

export interface CardData {
  card_id: number;
  id: number;
  coluna: Coluna;
  posicao: number;
  prazo: string;
  tem_notas: boolean;
  cargo: string;
  empresa: string;
  local: string;
  modelo: string;
  fonte: string;
  url: string;
  publicada_em: string | null;
  salario_min: number | null;
  salario_max: number | null;
  salario_intervalo: string;
  moeda: string;
  score: number | null;
  tag: "" | "quente" | "morna" | "fria";
  veredito: string;
  alertas: string[];
  motivo_descarte: string;
}

export interface Board {
  colunas: Record<Coluna, CardData[]>;
  novas_hoje: number;
  na_fila: number;
  atualizado_em: string | null;
  rodando: boolean;
  agenda: { intervalo_horas: number; ativo: boolean; ultima_execucao: string | null };
}

export interface Requisito {
  requisito: string;
  tipo: string;
  classificacao: "forte" | "parcial" | "lacuna" | "bloqueio";
  evidencia: string;
  fatos_ids: string[];
}

export interface Analise {
  veredito: string;
  score: number | null;
  tag: string;
  resumo: string;
  motivos: string[];
  requisitos: Requisito[];
  lacunas: string[];
  alertas: string[];
  motivos_descarte: string[];
  modelo: string;
  criado_em: string;
}

export interface JobDetail extends Omit<CardData, "card_id" | "coluna" | "posicao" | "prazo" | "tem_notas" | "score" | "tag" | "veredito" | "alertas" | "motivo_descarte"> {
  descricao: string;
  tipo: string;
  analise: Analise | null;
  card: { id: number; coluna: Coluna; notas: string; prazo: string } | null;
  historico: { de: string; para: string; autor: string; em: string }[];
  cvs: { id: number; criado_em: string; modelo: string; arquivo_base: string; nota: string }[];
}

export interface CV {
  id: number;
  job_id: number;
  cv_md: string;
  relatorio_md: string;
  diff_md: string;
  veracidade: { bullet: string; fatos_ids: string[] }[];
  mensagem_recrutador: string;
  validacao: { bullet: string; motivo: string }[];
  modelo: string;
  criado_em: string;
  arquivo_base: string;
  nota?: string;
  cv_base_md?: string;
}

export interface Run {
  id: number;
  origem: string;
  status: string;
  iniciado_em: string;
  terminado_em: string | null;
  buscas: number;
  encontradas: number;
  novas: number;
  analisadas: number;
  log: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

export async function api<T>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: opts.method ?? "GET",
    credentials: "same-origin",
    headers: opts.body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 401 && !path.startsWith("/auth/login")) onUnauthorized();
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const d = await res.json();
      msg = typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail);
    } catch {
      /* corpo vazio */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export function relTime(iso: string | null): string {
  if (!iso) return "nunca";
  const diff = (Date.now() - new Date(iso).getTime()) / 60000;
  if (diff < 1) return "agora";
  if (diff < 60) return `há ${Math.round(diff)} min`;
  if (diff < 60 * 24) return `há ${Math.round(diff / 60)} h`;
  return `há ${Math.round(diff / 1440)} dias`;
}

export function salario(j: { salario_min: number | null; salario_max: number | null; moeda: string; salario_intervalo: string }) {
  if (!j.salario_min && !j.salario_max) return "a confirmar";
  const f = (n: number | null) => (n ? n.toLocaleString("pt-BR", { maximumFractionDigits: 0 }) : "");
  const iv = { monthly: "/mês", yearly: "/ano", hourly: "/h", weekly: "/sem", daily: "/dia" }[j.salario_intervalo] ?? "";
  const range = j.salario_min && j.salario_max && j.salario_min !== j.salario_max ? `${f(j.salario_min)} a ${f(j.salario_max)}` : f(j.salario_max || j.salario_min);
  return `${j.moeda === "BRL" || !j.moeda ? "R$" : j.moeda} ${range}${iv}`;
}
