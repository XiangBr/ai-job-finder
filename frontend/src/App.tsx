import { useCallback, useEffect, useRef, useState } from "react";
import { api, relTime, setUnauthorizedHandler, type Board as BoardT } from "./api";
import AddJobModal from "./components/AddJobModal";
import Board from "./components/Board";
import JobPanel from "./components/JobPanel";
import Login from "./components/Login";
import Settings from "./components/Settings";
import { Button, Spinner, useToast } from "./components/ui";

type Tab = "quadro" | "config";

export default function App() {
  const [user, setUser] = useState<string | null | undefined>(undefined);
  const [tab, setTab] = useState<Tab>("quadro");
  const [board, setBoard] = useState<BoardT | null>(null);
  const [openJob, setOpenJob] = useState<number | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [, setTick] = useState(0);
  const toast = useToast();
  const wasRunning = useRef(false);

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    api<{ username: string }>("/auth/me").then((d) => setUser(d.username)).catch(() => setUser(null));
  }, []);

  const load = useCallback(async () => {
    try {
      const b = await api<BoardT>("/board");
      setBoard(b);
      if (wasRunning.current && !b.rodando) toast(`Busca concluída · ${b.novas_hoje} vagas novas hoje`);
      wasRunning.current = b.rodando;
    } catch {
      /* 401 tratado pelo handler */
    }
  }, [toast]);

  useEffect(() => {
    if (!user) return;
    load();
    const t = setInterval(() => {
      load();
      setTick((x) => x + 1);
    }, wasRunning.current ? 5000 : 30000);
    return () => clearInterval(t);
  }, [user, load, board?.rodando]);

  async function buscarAgora() {
    try {
      await api("/runs", { method: "POST" });
      toast("Busca iniciada. As vagas aparecem em alguns minutos", "info");
      wasRunning.current = true;
      load();
    } catch (e) {
      toast((e as Error).message, "erro");
    }
  }

  async function logout() {
    await api("/auth/logout", { method: "POST" });
    setUser(null);
  }

  if (user === undefined) return <div className="grid h-full place-items-center"><Spinner className="h-6 w-6 text-indigo-500" /></div>;
  if (user === null) return <Login onLogin={setUser} />;

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
        <div className="flex items-center gap-2">
          <img src="/favicon.svg" className="h-7 w-7" alt="" />
          <span className="font-semibold tracking-wide text-slate-900">AI-JOB-FINDER</span>
        </div>
        <nav className="flex gap-1">
          {(["quadro", "config"] as Tab[]).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`rounded-lg px-3 py-1.5 text-sm ${tab === t ? "bg-slate-100 font-medium text-slate-900" : "text-slate-500 hover:text-slate-800"}`}>
              {t === "quadro" ? "Quadro" : "Currículo e filtros"}
            </button>
          ))}
        </nav>
        <div className="ml-auto flex flex-wrap items-center gap-3 text-sm text-slate-500">
          {board && (
            <>
              <span><b className="text-slate-800">{board.novas_hoje}</b> vagas novas hoje</span>
              {board.na_fila > 0 && (
                <span title="Vagas encontradas que ainda vão passar pela análise da IA">
                  · <b className="text-slate-800">{board.na_fila}</b> na fila de análise
                </span>
              )}
              <span className="hidden sm:inline">atualizado {relTime(board.atualizado_em)}</span>
            </>
          )}
          <Button variant="outline" onClick={() => setAddOpen(true)}>+ Vaga manual</Button>
          <Button onClick={buscarAgora} disabled={board?.rodando}>
            {board?.rodando ? <><Spinner /> Buscando…</> : "Buscar agora"}
          </Button>
          <button onClick={logout} className="text-slate-400 hover:text-slate-700" title="Sair">{user} · sair</button>
        </div>
      </header>

      <main className="min-h-0 flex-1">
        {tab === "quadro" ? (
          board ? <Board board={board} onOpen={setOpenJob} onChange={load} /> : <div className="grid h-full place-items-center"><Spinner className="h-6 w-6 text-indigo-500" /></div>
        ) : (
          <Settings onSaved={load} />
        )}
      </main>

      {openJob != null && <JobPanel jobId={openJob} onClose={() => setOpenJob(null)} onChange={load} />}
      {addOpen && <AddJobModal onClose={() => setAddOpen(false)} onAdded={(id) => { setAddOpen(false); load(); setOpenJob(id); }} />}
    </div>
  );
}
