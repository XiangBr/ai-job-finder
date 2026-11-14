import { useEffect, useState } from "react";
import { api, relTime, type Run } from "../api";
import CurriculoTab from "./CurriculoTab";
import FiltersForm from "./FiltersForm";
import { Badge, Button, Spinner, useToast } from "./ui";

interface Profile { nome: string; fatos_yaml: string; cv_base_md: string; filtros_yaml: string }
interface Schedule { intervalo_horas: number; ativo: boolean; ultima_execucao: string | null }

type Sec = "filtros" | "curriculo" | "fatos" | "yaml";
type TextSec = "fatos" | "yaml";

const TABS: [Sec, string][] = [["curriculo", "Currículo"], ["filtros", "Filtros de busca"], ["fatos", "Fatos (fatos.yaml)"], ["yaml", "filtros.yaml (avançado)"]];
const FIELD: Record<TextSec, keyof Profile> = { fatos: "fatos_yaml", yaml: "filtros_yaml" };
const HELP: Record<TextSec, string> = {
  fatos: "Banco de fatos verdadeiros. O CV adaptado só pode usar o que está aqui; cada bullet aponta para um ID. Troque [[...]] e status: pendente pelos números reais.",
  yaml: "Os mesmos filtros da aba Filtros de busca, em YAML. Use só se precisar de algo que o formulário não tem.",
};

export default function Settings({ onSaved }: { onSaved: () => void }) {
  const [p, setP] = useState<Profile | null>(null);
  const [sch, setSch] = useState<Schedule | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [sec, setSec] = useState<Sec>("curriculo");
  const [saving, setSaving] = useState(false);
  const [formKey, setFormKey] = useState(0);
  const toast = useToast();

  useEffect(() => {
    api<Schedule>("/schedule").then(setSch);
    api<{ runs: Run[] }>("/runs").then((d) => setRuns(d.runs));
  }, []);
  useEffect(() => {
    if (sec === "fatos" || sec === "yaml") api<Profile>("/profile").then(setP);
  }, [sec]);

  async function saveText() {
    if (!p || (sec !== "fatos" && sec !== "yaml")) return;
    setSaving(true);
    try {
      setP(await api<Profile>("/profile", { method: "PUT", body: { [FIELD[sec]]: p[FIELD[sec]] } }));
      toast("Salvo. As próximas análises usam a versão nova");
      if (sec === "yaml") setFormKey((k) => k + 1);
      onSaved();
    } catch (e) {
      toast((e as Error).message, "erro");
    } finally {
      setSaving(false);
    }
  }

  async function saveSchedule(patch: Partial<Schedule>) {
    try {
      setSch(await api<Schedule>("/schedule", { method: "PUT", body: patch }));
      toast("Agenda atualizada");
      onSaved();
    } catch (e) {
      toast((e as Error).message, "erro");
    }
  }

  const opts = [1, 2, 3, 4, 6, 8, 12, 24, 48];

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[1fr_300px]">
        <div className="min-w-0">
          <div className="mb-4 flex flex-wrap gap-1">
            {TABS.map(([k, label]) => (
              <button key={k} onClick={() => setSec(k)}
                className={`rounded-lg px-3 py-1.5 text-sm ${sec === k ? "bg-white font-medium text-slate-900 shadow-sm ring-1 ring-slate-200" : "text-slate-500 hover:text-slate-800"}`}>
                {label}
              </button>
            ))}
          </div>

          {sec === "filtros" ? (
            <FiltersForm key={formKey} onSaved={onSaved} />
          ) : sec === "curriculo" ? (
            <CurriculoTab onSaved={onSaved} />
          ) : !p ? (
            <div className="grid h-64 place-items-center"><Spinner className="h-6 w-6 text-indigo-500" /></div>
          ) : (
            <section className="flex min-h-[70vh] flex-col rounded-2xl border border-slate-200 bg-white">
              <div className="flex items-center gap-3 border-b border-slate-100 px-4 py-3">
                <p className="flex-1 text-xs text-slate-500">{HELP[sec]}</p>
                <Button onClick={saveText} disabled={saving}>{saving ? "Salvando…" : "Salvar"}</Button>
              </div>
              <textarea value={p[FIELD[sec]]} onChange={(e) => setP({ ...p, [FIELD[sec]]: e.target.value })} spellCheck={false}
                className="m-3 flex-1 resize-none rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-xs leading-relaxed outline-none focus:border-indigo-300" />
            </section>
          )}
        </div>

        <aside className="space-y-6 lg:sticky lg:top-6 lg:self-start">
          {sch && (
            <section className="rounded-2xl border border-slate-200 bg-white p-4">
              <h3 className="mb-3 text-sm font-semibold text-slate-900">Busca automática</h3>
              <label className="mb-3 flex items-center gap-2 text-sm">
                <input type="checkbox" checked={sch.ativo} onChange={(e) => saveSchedule({ ativo: e.target.checked })} />
                Ativa
              </label>
              <label className="mb-1 block text-xs text-slate-500">Frequência</label>
              <select value={sch.intervalo_horas} onChange={(e) => saveSchedule({ intervalo_horas: Number(e.target.value) })}
                className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm">
                {opts.map((h) => <option key={h} value={h}>a cada {h} h</option>)}
                {!opts.includes(sch.intervalo_horas) && <option value={sch.intervalo_horas}>a cada {sch.intervalo_horas} h</option>}
              </select>
              <p className="mt-2 text-xs text-slate-500">Última execução: {relTime(sch.ultima_execucao)}</p>
            </section>
          )}

          <section className="rounded-2xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-900">Execuções recentes</h3>
            {runs.length === 0 && <p className="text-xs text-slate-500">Nenhuma ainda.</p>}
            <ul className="space-y-2">
              {runs.map((r) => (
                <li key={r.id}>
                  <details className="text-xs">
                    <summary className="flex cursor-pointer items-center gap-2">
                      <Badge tone={r.status === "ok" ? "green" : r.status === "erro" ? "red" : "indigo"}>{r.status}</Badge>
                      <span className="text-slate-600">{relTime(r.iniciado_em)} · {r.novas} novas · {r.analisadas} analisadas</span>
                    </summary>
                    <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-[11px] text-slate-600">{r.log || "(sem log)"}</pre>
                  </details>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  );
}
