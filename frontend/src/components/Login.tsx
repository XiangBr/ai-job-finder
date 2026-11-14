import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Button } from "./ui";

export default function Login({ onLogin }: { onLogin: (u: string) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [erro, setErro] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErro("");
    setLoading(true);
    try {
      const d = await api<{ username: string }>("/auth/login", { method: "POST", body: { username, password } });
      onLogin(d.username);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid h-full place-items-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-7 shadow-sm">
        <div className="mb-6 flex items-center gap-2">
          <img src="/favicon.svg" className="h-10 w-10" alt="AI-JOB-FINDER" />
          <div>
            <div className="font-semibold tracking-wide text-slate-900">AI-JOB-FINDER</div>
            <div className="text-xs text-slate-500">Vagas analisadas e CVs adaptados com IA</div>
          </div>
        </div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Usuário</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus autoComplete="username"
          className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500" />
        <label className="mb-1 block text-xs font-medium text-slate-600">Senha</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password"
          className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500" />
        {erro && <p className="mb-3 text-sm text-red-600">{erro}</p>}
        <Button type="submit" disabled={loading || !username || !password} className="w-full py-2">Entrar</Button>
      </form>
    </div>
  );
}
