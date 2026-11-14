import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Button, useToast } from "./ui";

export default function AddJobModal({ onClose, onAdded }: { onClose: () => void; onAdded: (id: number) => void }) {
  const [f, setF] = useState({ cargo: "", empresa: "", local: "", url: "", descricao: "", modelo: "" });
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  async function submit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const d = await api<{ id: number }>("/jobs/manual", { method: "POST", body: f });
      toast("Vaga adicionada. A análise roda em segundo plano", "info");
      onAdded(d.id);
    } catch (err) {
      toast((err as Error).message, "erro");
    } finally {
      setSaving(false);
    }
  }

  const input = "w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-400";
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/30 px-4" onClick={onClose}>
      <form onSubmit={submit} onClick={(e) => e.stopPropagation()} className="w-full max-w-lg space-y-3 rounded-2xl bg-white p-6 shadow-xl">
        <div>
          <h2 className="font-semibold text-slate-900">Adicionar vaga manualmente</h2>
          <p className="text-xs text-slate-500">Para vagas que o JobSpy não pega (Gupy, site da empresa). Cole a descrição completa.</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <input required placeholder="Cargo" value={f.cargo} onChange={(e) => setF({ ...f, cargo: e.target.value })} className={input} />
          <input required placeholder="Empresa" value={f.empresa} onChange={(e) => setF({ ...f, empresa: e.target.value })} className={input} />
          <input placeholder="Local (ex.: Curitiba, PR)" value={f.local} onChange={(e) => setF({ ...f, local: e.target.value })} className={input} />
          <select value={f.modelo} onChange={(e) => setF({ ...f, modelo: e.target.value })} className={input}>
            <option value="">Modelo (detectar)</option>
            <option value="remoto">Remoto</option>
            <option value="hibrido">Híbrido</option>
            <option value="presencial">Presencial</option>
          </select>
        </div>
        <input placeholder="Link da vaga" value={f.url} onChange={(e) => setF({ ...f, url: e.target.value })} className={input} />
        <textarea required rows={10} placeholder="Descrição da vaga" value={f.descricao} onChange={(e) => setF({ ...f, descricao: e.target.value })} className={input} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={saving}>{saving ? "Salvando…" : "Adicionar e analisar"}</Button>
        </div>
      </form>
    </div>
  );
}
