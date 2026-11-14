"""Servidor MCP (Streamable HTTP em /mcp) para o Hermes ou o Claude usarem o app por chat.

Autenticação: header `Authorization: Bearer <MCP_TOKEN>`.
"""

import hmac
import json

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from sqlmodel import Session, select

from . import collector, pipeline, services
from . import cv as cvmod
from .ai.providers import AIError
from .config import get_settings
from .db import engine
from .filters import detect_modelo
from .models import COLUMNS, Card, Job
from .profile import get_schedule, mcp_profile, profile_has_job

mcp = MCPServer(
    name="ai-job-finder",
    instructions=(
        "Kanban de vagas da pessoa candidata. Use board_summary para ver o quadro, get_job para detalhes, "
        "move_card quando a pessoa avançar no processo, search_jobs_live para buscar vagas sob demanda e "
        "tailor_cv para gerar um CV adaptado. O app nunca se candidata: a candidatura é sempre da própria pessoa. "
        f"Colunas: {', '.join(COLUMNS)}."
    ),
)


def _j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str, indent=1)


def _sync(fn, *args):
    return anyio.to_thread.run_sync(lambda: fn(*args))


@mcp.tool()
async def board_summary(coluna: str = "", limite: int = 30) -> str:
    """Resumo do kanban: contagem por coluna e os cards (cargo, empresa, score, tag, alertas).
    Passe `coluna` para listar só uma (selecionadas, candidatura, entrevista, desafio, aprovado, descartadas)."""

    def run():
        with Session(engine) as s:
            b = services.board(s, mcp_profile(s))
        cols = b["colunas"]
        out = {
            "novas_hoje": b["novas_hoje"], "atualizado_em": b["atualizado_em"], "rodando": b["rodando"],
            "contagem": {k: len(v) for k, v in cols.items()},
        }
        keep = ("card_id", "id", "cargo", "empresa", "local", "modelo", "score", "tag", "alertas", "motivo_descarte", "url")
        sel = [coluna] if coluna else [c for c in COLUMNS if c != "descartadas"]
        out["cards"] = {c: [{k: x[k] for k in keep} for x in cols.get(c, [])[:limite]] for c in sel}
        return _j(out)

    return await _sync(run)


@mcp.tool()
async def get_job(job_id: int) -> str:
    """Detalhes de uma vaga: descrição, pré-análise da IA (score, requisitos, lacunas), card, histórico e CVs gerados."""

    def run():
        with Session(engine) as s:
            d = services.job_detail(s, job_id, mcp_profile(s))
        return _j(d) if d else "vaga não existe"

    return await _sync(run)


@mcp.tool()
async def move_card(job_id: int, coluna: str, nota: str = "") -> str:
    """Move o card da vaga para outra coluna (ex.: 'candidatura' depois que ela se candidatou). `nota` é anexada às notas."""

    def run():
        with Session(engine) as s:
            card = s.exec(select(Card).where(Card.job_id == job_id, Card.profile_id == mcp_profile(s).id)).first()
            if not card:
                return "card não existe"
            notas = (card.notas + "\n" + nota).strip() if nota else None
            try:
                services.update_card(s, card, "mcp", coluna=coluna, notas=notas)
            except ValueError as e:
                return str(e)
            return f"ok: vaga {job_id} em '{coluna}'"

    return await _sync(run)


@mcp.tool()
async def run_search_now() -> str:
    """Dispara a busca agendada agora (JobSpy + análise). Roda em segundo plano."""
    with Session(engine) as s:
        profile_id = mcp_profile(s).id
    started = pipeline.run_in_background(profile_id, "mcp")
    return "busca iniciada" if started else "já existe uma busca rodando"


@mcp.tool()
async def search_jobs_live(termo: str, local: str = "Brazil", remoto: bool = False, horas: int = 72,
                           salvar: bool = False) -> str:
    """Busca vagas sob demanda no LinkedIn e Indeed (JobSpy), sem esperar a agenda.
    Com salvar=True, as vagas novas entram no quadro e passam pela análise."""

    def run():
        rows = collector.scrape({
            "search_term": termo, "location": local, "is_remote": remoto,
            "hours_old": horas, "sites": ["linkedin", "indeed"],
        })
        jobs = [collector.row_to_job(r, termo, remoto) for r in rows]
        if salvar:
            with Session(engine) as s:
                profile = mcp_profile(s)
                novas = collector.save_new(s, jobs, profile.id)
                for j in novas:
                    try:
                        pipeline.analyze(s, j, profile)
                    except AIError:
                        s.rollback()
            return _j({"encontradas": len(jobs), "novas_no_quadro": len(novas)})
        return _j([
            {"cargo": j.cargo, "empresa": j.empresa, "local": j.local, "modelo": j.modelo,
             "url": j.url, "publicada_em": j.publicada_em, "descricao": j.descricao[:400]}
            for j in jobs
        ])

    return await _sync(run)


@mcp.tool()
async def add_job(cargo: str, empresa: str, descricao: str, local: str = "", url: str = "") -> str:
    """Adiciona uma vaga manualmente (ex.: da Gupy) e roda a análise de fit."""

    def run():
        with Session(engine) as s:
            h = collector.job_hash(empresa, cargo, local)
            u = url or f"manual:{h[:16]}"
            profile = mcp_profile(s)
            job = s.exec(select(Job).where((Job.hash == h) | (Job.url == u))).first()
            if job and profile_has_job(s, profile.id, job.id):
                return "essa vaga já está no quadro"
            job = job or Job(hash=h, fonte="manual", url=u, cargo=cargo, empresa=empresa, local=local,
                      modelo=detect_modelo(cargo, descricao, None, local), descricao=descricao)
            s.add(job)
            s.commit()
            s.refresh(job)
            try:
                a = pipeline.analyze(s, job, profile)
            except AIError as e:
                return f"vaga salva (id {job.id}), mas a análise falhou: {e}"
            return _j({"job_id": job.id, "veredito": a.veredito, "score": a.score, "tag": a.tag})

    return await _sync(run)


@mcp.tool()
async def tailor_cv(job_id: int) -> str:
    """Gera o CV adaptado para a vaga (com validação de veracidade). Pode levar 1 a 3 minutos.
    Devolve o markdown do CV, a mensagem ao recrutador e o link de download relativo."""

    def run():
        with Session(engine) as s:
            job = s.get(Job, job_id)
            profile = mcp_profile(s)
            if not job or not profile_has_job(s, profile.id, job_id):
                return "vaga não existe"
            try:
                g = cvmod.tailor(s, job, profile, services.latest_analysis(s, job.id, profile.id))
            except AIError as e:
                return f"falhou: {e}"
            d = services.cv_dict(g)
        return _j({
            "cv_id": d["id"], "cv_md": d["cv_md"], "mensagem_recrutador": d["mensagem_recrutador"],
            "bullets_removidos": d["validacao"],
            "download_docx": f"/api/cvs/{d['id']}/download?format=docx",
            "download_pdf": f"/api/cvs/{d['id']}/download?format=pdf",
        })

    return await _sync(run)


@mcp.tool()
async def get_settings_info() -> str:
    """Mostra a agenda (intervalo, ativo, última execução) e o filtros.yaml atual."""

    def run():
        with Session(engine) as s:
            p = mcp_profile(s)
            sch = get_schedule(s, p)
            return _j({"agenda": sch.model_dump(), "filtros_yaml": p.filtros_yaml})

    return await _sync(run)


@mcp.tool()
async def set_schedule(intervalo_horas: float, ativo: bool = True) -> str:
    """Altera a frequência da busca automática (mínimo 1 hora)."""
    if intervalo_horas < 1:
        return "intervalo mínimo: 1 hora"

    def run():
        with Session(engine) as s:
            sch = get_schedule(s, mcp_profile(s))
            sch.intervalo_horas, sch.ativo = intervalo_horas, ativo
            s.add(sch)
            s.commit()
        return f"agenda: a cada {intervalo_horas} h, {'ativa' if ativo else 'pausada'}"

    return await _sync(run)


# ------------------------------------------------------------------ app ASGI

mcp_http_app = mcp.streamable_http_app(
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


class Router:
    """Despacha /mcp para o servidor MCP (com bearer token) e o resto para o FastAPI."""

    def __init__(self, web_app):
        self.web = web_app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] == "http" and (path == "/mcp" or path.startswith("/mcp/")):
            token = get_settings().mcp_token
            if not token:
                return await _plain(send, 404, "MCP desligado (defina MCP_TOKEN)")
            auth = dict(scope.get("headers") or []).get(b"authorization", b"").decode()
            if not hmac.compare_digest(auth, f"Bearer {token}"):
                return await _plain(send, 401, "token inválido")
            scope = {**scope, "path": "/mcp"}
            return await mcp_http_app(scope, receive, send)
        return await self.web(scope, receive, send)


async def _plain(send, status: int, msg: str):
    body = msg.encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"text/plain; charset=utf-8"), (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})
