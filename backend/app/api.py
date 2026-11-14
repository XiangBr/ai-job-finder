import hashlib
import threading
import time

import anyio
import yaml
from fastapi import APIRouter, Depends, HTTPException, Form, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from . import cv as cvmod
from . import cv_chat, cv_import
from . import pipeline, services
from .ai.providers import AIError, get_provider
from .filters_form import FiltrosForm, form_to_yaml, yaml_to_form
from .auth import COOKIE, check_password, current_user, make_token
from .config import get_settings
from .db import engine, get_session
from .filters import detect_modelo
from .models import Card, GeneratedCV, Job, Profile, Run, User, now
from .profile import get_profile, get_schedule, link_job, profile_has_job

router = APIRouter(prefix="/api")


def current_profile(user: User = Depends(current_user), session: Session = Depends(get_session)) -> Profile:
    """Cada usuário tem o próprio perfil: CV, fatos, filtros, agenda e kanban."""
    return get_profile(session, user)
auth_router = APIRouter(prefix="/api/auth")


# ------------------------------------------------------------------ auth

class LoginIn(BaseModel):
    username: str
    password: str


_fails: dict[str, list[float]] = {}


@auth_router.post("/login")
def login(body: LoginIn, request: Request, response: Response, session: Session = Depends(get_session)):
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?")
    t = time.time()
    recent = [x for x in _fails.get(ip, []) if t - x < 900]
    if len(recent) >= 10:
        raise HTTPException(429, "muitas tentativas; espere 15 minutos")
    user = session.exec(select(User).where(User.username == body.username.strip())).first()
    if not user or not check_password(body.password, user.password_hash):
        _fails[ip] = recent + [t]
        raise HTTPException(401, "usuário ou senha incorretos")
    _fails.pop(ip, None)
    s = get_settings()
    response.set_cookie(
        COOKIE, make_token(user), max_age=s.session_days * 86400, httponly=True,
        samesite="lax", secure=s.cookie_secure,
    )
    return {"username": user.username}


@auth_router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok": True}


@auth_router.get("/me")
def me(user: User = Depends(current_user)):
    return {"username": user.username, "ai_provider": get_settings().ai_provider}


# ------------------------------------------------------------------ perfil, filtros, agenda

class ProfileIn(BaseModel):
    nome: str | None = None
    fatos_yaml: str | None = None
    cv_base_md: str | None = None
    filtros_yaml: str | None = None
    regras_cv: str | None = None


def _check_yaml(text: str, campo: str):
    try:
        yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise HTTPException(422, f"{campo} inválido: {e}")


@router.get("/profile")
def get_prof(p: Profile = Depends(current_profile)):
    return p.model_dump()


@router.put("/profile")
def put_prof(body: ProfileIn, session: Session = Depends(get_session), p: Profile = Depends(current_profile)):
    for campo in ("fatos_yaml", "filtros_yaml"):
        if getattr(body, campo) is not None:
            _check_yaml(getattr(body, campo), campo)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    p.atualizado_em = now()
    session.add(p)
    session.commit()
    return p.model_dump()


@router.post("/profile/cv-upload")
async def cv_upload(file: UploadFile, modo: str = Form("otimizar"), p: Profile = Depends(current_profile)):
    """Recebe o CV (PDF/DOCX/DOC), extrai o texto e devolve a prévia gerada pela IA. Não salva o perfil."""
    data = await file.read()
    try:
        texto = cv_import.extract_text(file.filename or "cv", data)
    except cv_import.ImportError_ as e:
        raise HTTPException(422, str(e))
    cv_import.save_original(p.id, file.filename or "cv", data)
    filtros = p.filtros_yaml

    def work():
        return cv_import.run_import(texto, filtros, "como_esta" if modo == "como_esta" else "otimizar")

    try:
        out, modelo = await anyio.to_thread.run_sync(work)
    except AIError as e:
        raise HTTPException(502, str(e))
    except yaml.YAMLError:
        raise HTTPException(502, "A IA devolveu um banco de fatos inválido. Tente de novo.")
    return {"arquivo": file.filename, "modo": modo, "caracteres": len(texto), "texto_extraido": texto[:30000],
            "modelo": modelo, **out.model_dump()}


class CVChatIn(BaseModel):
    mensagem: str
    historico: list[dict] = []
    # rascunho atual (ainda não salvo); se vier vazio, usa o perfil salvo
    fatos_yaml: str | None = None
    cv_base_md: str | None = None
    regras_cv: str | None = None


@router.post("/profile/cv-chat")
def cv_chat_endpoint(body: CVChatIn, p: Profile = Depends(current_profile)):
    """A pessoa informa fatos ou pede alterações; devolve fatos + CV base atualizados (não salva)."""
    if not body.mensagem.strip():
        raise HTTPException(422, "escreva uma mensagem")
    fatos = body.fatos_yaml if body.fatos_yaml is not None else p.fatos_yaml
    cv = body.cv_base_md if body.cv_base_md is not None else p.cv_base_md
    regras = body.regras_cv if body.regras_cv is not None else p.regras_cv
    try:
        out, modelo = cv_chat.run(body.mensagem, fatos, cv, body.historico, regras)
    except AIError as e:
        raise HTTPException(502, str(e))
    except yaml.YAMLError:
        raise HTTPException(502, "A IA devolveu um banco de fatos inválido. Tente de novo.")
    return {**out.model_dump(), "modelo": modelo}


@router.get("/profile/cv-original")
def cv_original(p: Profile = Depends(current_profile)):
    f = cv_import.original_file(p.id)
    if not f:
        raise HTTPException(404, "nenhum currículo enviado ainda")
    return FileResponse(f[0], filename=f[1])


@router.get("/profile/cv-original/info")
def cv_original_info(p: Profile = Depends(current_profile)):
    f = cv_import.original_file(p.id)
    return {"nome": f[1] if f else None}


class FiltersIn(BaseModel):
    filtros_yaml: str


@router.get("/filters")
def get_filters(p: Profile = Depends(current_profile)):
    return {"filtros_yaml": p.filtros_yaml}


@router.put("/filters")
def put_filters(body: FiltersIn, session: Session = Depends(get_session), p: Profile = Depends(current_profile)):
    _check_yaml(body.filtros_yaml, "filtros.yaml")
    p.filtros_yaml = body.filtros_yaml
    p.atualizado_em = now()
    session.add(p)
    session.commit()
    return {"filtros_yaml": p.filtros_yaml}


@router.get("/filters/form")
def get_filters_form(p: Profile = Depends(current_profile)):
    return yaml_to_form(p.filtros_yaml).model_dump()


@router.put("/filters/form")
def put_filters_form(body: FiltrosForm, session: Session = Depends(get_session), p: Profile = Depends(current_profile)):
    p.filtros_yaml = form_to_yaml(body, p.filtros_yaml)
    p.atualizado_em = now()
    session.add(p)
    session.commit()
    return yaml_to_form(p.filtros_yaml).model_dump()


class FillIn(BaseModel):
    texto: str
    form: FiltrosForm
    historico: list[dict] = []


@router.post("/filters/ai-fill")
def ai_fill(body: FillIn, _: User = Depends(current_user)):
    """A IA lê a descrição em texto livre e devolve o formulário preenchido (não salva)."""
    if not body.texto.strip():
        raise HTTPException(422, "escreva o que você procura")
    try:
        out, modelo = get_provider().fill_filters(body.texto, body.form, body.historico)
    except AIError as e:
        raise HTTPException(502, str(e))
    return {**out.model_dump(), "modelo": modelo}


class ScheduleIn(BaseModel):
    intervalo_horas: float | None = None
    ativo: bool | None = None


@router.get("/schedule")
def get_sched(session: Session = Depends(get_session), p: Profile = Depends(current_profile)):
    return get_schedule(session, p).model_dump()


@router.put("/schedule")
def put_sched(body: ScheduleIn, session: Session = Depends(get_session), p: Profile = Depends(current_profile)):
    sch = get_schedule(session, p)
    if body.intervalo_horas is not None:
        if body.intervalo_horas < 1:
            raise HTTPException(422, "intervalo mínimo: 1 hora")
        sch.intervalo_horas = body.intervalo_horas
    if body.ativo is not None:
        sch.ativo = body.ativo
    session.add(sch)
    session.commit()
    return sch.model_dump()


# ------------------------------------------------------------------ execuções

@router.post("/runs")
def start_run(p: Profile = Depends(current_profile)):
    if not p.filtros_yaml.strip():
        raise HTTPException(422, "defina os filtros de busca antes")
    if not pipeline.run_in_background(p.id, "manual"):
        raise HTTPException(409, "já existe uma busca rodando")
    return {"ok": True}


@router.get("/runs")
def list_runs(session: Session = Depends(get_session), p: Profile = Depends(current_profile)):
    runs = session.exec(select(Run).where(Run.profile_id == p.id).order_by(Run.id.desc()).limit(15)).all()
    return {"rodando": pipeline.is_running(), "runs": [r.model_dump() for r in runs]}


# ------------------------------------------------------------------ kanban

@router.get("/board")
def get_board(session: Session = Depends(get_session), p: Profile = Depends(current_profile)):
    return services.board(session, p)


class CardPatch(BaseModel):
    coluna: str | None = None
    posicao: float | None = None
    notas: str | None = None
    prazo: str | None = None


@router.patch("/cards/{card_id}")
def patch_card(card_id: int, body: CardPatch, session: Session = Depends(get_session),
               user: User = Depends(current_user), p: Profile = Depends(current_profile)):
    card = session.get(Card, card_id)
    if not card or card.profile_id != p.id:
        raise HTTPException(404, "card não existe")
    try:
        card = services.update_card(session, card, user.username, **body.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))
    return card.model_dump()


# ------------------------------------------------------------------ vagas e CVs

@router.get("/jobs/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session), p: Profile = Depends(current_profile)):
    d = services.job_detail(session, job_id, p)
    if not d:
        raise HTTPException(404, "vaga não existe")
    return d


class ManualJobIn(BaseModel):
    cargo: str
    empresa: str
    local: str = ""
    url: str = ""
    descricao: str
    modelo: str = ""


@router.post("/jobs/manual")
def add_manual_job(body: ManualJobIn, session: Session = Depends(get_session), p: Profile = Depends(current_profile)):
    """Para vagas fora do JobSpy (ex.: Gupy): cola a descrição e o app analisa."""
    from .collector import job_hash

    url = body.url.strip() or f"manual:{hashlib.sha1(body.descricao.encode()).hexdigest()[:16]}"
    h = job_hash(body.empresa, body.cargo, body.local)
    job = session.exec(select(Job).where((Job.hash == h) | (Job.url == url))).first()
    if job and profile_has_job(session, p.id, job.id):
        raise HTTPException(409, "essa vaga já está no quadro")
    job = job or Job(
        hash=h, fonte="manual", url=url, cargo=body.cargo, empresa=body.empresa, local=body.local,
        modelo=body.modelo or detect_modelo(body.cargo, body.descricao, None, body.local),
        descricao=body.descricao, publicada_em=now(),
    )
    session.add(job)
    session.flush()
    link_job(session, p.id, job.id)
    session.commit()
    session.refresh(job)

    def bg(job_id: int, profile_id: int):
        with Session(engine) as s:
            try:
                pipeline.analyze(s, s.get(Job, job_id), s.get(Profile, profile_id))
            except AIError:
                pass

    threading.Thread(target=bg, args=(job.id, p.id), daemon=True).start()
    return {"id": job.id}


@router.post("/jobs/{job_id}/analyze")
def reanalyze(job_id: int, session: Session = Depends(get_session), profile: Profile = Depends(current_profile)):
    job = session.get(Job, job_id)
    if not job or not profile_has_job(session, profile.id, job_id):
        raise HTTPException(404, "vaga não existe")
    try:
        pipeline.analyze(session, job, profile)
    except AIError as e:
        raise HTTPException(502, str(e))
    return services.job_detail(session, job_id, profile)


@router.post("/jobs/{job_id}/tailor-cv")
def tailor_cv(job_id: int, session: Session = Depends(get_session), profile: Profile = Depends(current_profile)):
    job = session.get(Job, job_id)
    if not job or not profile_has_job(session, profile.id, job_id):
        raise HTTPException(404, "vaga não existe")
    if not profile.fatos_yaml.strip() or not profile.cv_base_md.strip():
        raise HTTPException(422, "perfil sem fatos.yaml ou CV base")
    analise = services.latest_analysis(session, job.id, profile.id)
    try:
        g = cvmod.tailor(session, job, profile, analise)
    except AIError as e:
        raise HTTPException(502, str(e))
    return services.cv_dict(g)


@router.get("/cvs/{cv_id}")
def get_cv(cv_id: int, session: Session = Depends(get_session), p: Profile = Depends(current_profile)):
    g = session.get(GeneratedCV, cv_id)
    if not g or g.profile_id != p.id:
        raise HTTPException(404, "CV não existe")
    d = services.cv_dict(g)
    d["cv_base_md"] = p.cv_base_md
    return d


class CVEditIn(BaseModel):
    mensagem: str
    historico: list[dict] = []


@router.post("/cvs/{cv_id}/chat")
def cv_edit_chat(cv_id: int, body: CVEditIn, session: Session = Depends(get_session),
                 p: Profile = Depends(current_profile)):
    """Ajusta este CV a pedido da pessoa. Se mudar, cria uma nova versão (as anteriores continuam)."""
    g = session.get(GeneratedCV, cv_id)
    if not g or g.profile_id != p.id:
        raise HTTPException(404, "CV não existe")
    if not body.mensagem.strip():
        raise HTTPException(422, "escreva o que quer mudar")
    job = session.get(Job, g.job_id)
    try:
        r = cvmod.edit(session, g, job, p, body.mensagem, body.historico)
    except AIError as e:
        raise HTTPException(502, str(e))
    cv = None
    if r["cv"] is not None:
        cv = services.cv_dict(r["cv"])
        cv["cv_base_md"] = p.cv_base_md
    return {"resposta": r["resposta"], "mudancas": r["mudancas"], "validacao": r["validacao"], "cv": cv}


@router.get("/cvs/{cv_id}/download")
def download_cv(cv_id: int, format: str = "docx", session: Session = Depends(get_session),
                p: Profile = Depends(current_profile)):
    g = session.get(GeneratedCV, cv_id)
    if not g or g.profile_id != p.id:
        raise HTTPException(404, "CV não existe")
    if format not in ("docx", "pdf", "md"):
        raise HTTPException(422, "formato: docx, pdf ou md")
    if format == "md":
        return Response(g.cv_md, media_type="text/markdown",
                        headers={"Content-Disposition": f'attachment; filename="{g.arquivo_base}.md"'})
    path = cvmod.get_file(g, format)
    if not path:
        raise HTTPException(503, "PDF indisponível: LibreOffice não está instalado (rode via Docker)")
    return FileResponse(path, filename=path.name)
