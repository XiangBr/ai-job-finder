"""Execução completa: coleta → filtros em código → IA → card no kanban."""

import hashlib
import json
import logging
import threading
from datetime import timedelta

from sqlmodel import Session, func, select

from . import collector, filters
from .ai.providers import AIError, get_provider
from .config import get_settings
from .db import engine
from .models import Analysis, Card, CardEvent, Job, Profile, ProfileJob, Run, now
from .profile import get_schedule, link_job, load_filters

log = logging.getLogger(__name__)
_lock = threading.Lock()


def cache_key(job: Job, profile: Profile, model: str) -> str:
    h = hashlib.sha1()
    for part in (job.hash, job.descricao, profile.fatos_yaml, profile.filtros_yaml, model):
        h.update((part or "").encode())
        h.update(b"\x00")
    return h.hexdigest()


def _place_card(session: Session, job: Job, profile: Profile, coluna: str) -> Card:
    card = session.exec(select(Card).where(Card.job_id == job.id, Card.profile_id == profile.id)).first()
    if card:
        return card
    top = session.exec(
        select(func.min(Card.posicao)).where(Card.profile_id == profile.id, Card.coluna == coluna)
    ).first()
    card = Card(job_id=job.id, profile_id=profile.id, coluna=coluna, posicao=(top or 0) - 1)
    session.add(card)
    session.flush()
    session.add(CardEvent(card_id=card.id, de="", para=coluna, autor="sistema"))
    return card


def analyze(session: Session, job: Job, profile: Profile) -> Analysis:
    link_job(session, profile.id, job.id)
    filtros = load_filters(profile)
    fc = filters.check(job, filtros)
    provider = get_provider()
    s = get_settings()
    key = cache_key(job, profile, f"{provider.name}:{s.ai_model_triage}")

    if fc["veredito"] == "DESCARTADA":
        a = Analysis(
            job_id=job.id, profile_id=profile.id, cache_key=key, veredito="DESCARTADA",
            filtro_motivos_json=json.dumps(fc["motivos"], ensure_ascii=False),
            alertas_json=json.dumps(fc["alertas"], ensure_ascii=False), modelo="filtro",
            resumo="; ".join(fc["motivos"]),
        )
        session.add(a)
        _place_card(session, job, profile, "descartadas")
        session.commit()
        return a

    cached = session.exec(select(Analysis).where(Analysis.cache_key == key, Analysis.modelo != "filtro")).first()
    if cached:
        result = None
        a = Analysis(**{k: v for k, v in cached.model_dump().items() if k not in ("id", "job_id", "criado_em")}, job_id=job.id)
    else:
        result, modelo = provider.analyze_job(job, profile.fatos_yaml, profile.filtros_yaml, fc)
        alertas = list(dict.fromkeys(fc["alertas"] + result.alertas))
        veredito = result.veredito
        if veredito != "DESCARTADA" and alertas and any(x != "salário a confirmar" for x in alertas):
            veredito = "ALERTA"
        a = Analysis(
            job_id=job.id, profile_id=profile.id, cache_key=key, veredito=veredito,
            filtro_motivos_json=json.dumps([result.motivo_descarte] if result.motivo_descarte else [], ensure_ascii=False),
            score=max(0, min(100, result.score)), tag=filters.tag_for(result.score),
            resumo=result.problema_empregador,
            motivos_json=json.dumps(result.motivos, ensure_ascii=False),
            requisitos_json=json.dumps([r.model_dump() for r in result.requisitos], ensure_ascii=False),
            lacunas_json=json.dumps(result.lacunas, ensure_ascii=False),
            alertas_json=json.dumps(alertas, ensure_ascii=False),
            modelo=modelo,
        )
    session.add(a)
    if a.veredito == "DESCARTADA" or (a.score is not None and a.score < 50):
        if a.veredito != "DESCARTADA":
            a.filtro_motivos_json = json.dumps([f"score baixo ({a.score})"], ensure_ascii=False)
        coluna = "descartadas"
    else:
        coluna = "selecionadas"
    _place_card(session, job, profile, coluna)
    session.commit()
    return a


def pending_query(profile: Profile):
    """Vagas encontradas para o perfil e ainda não analisadas por ele."""
    analyzed = select(Analysis.job_id).where(Analysis.profile_id == profile.id)
    mine = select(ProfileJob.job_id).where(ProfileJob.profile_id == profile.id)
    return Job.id.in_(mine), Job.id.not_in(analyzed)


def pending_jobs(session: Session, profile: Profile, limit: int) -> list[Job]:
    return list(session.exec(select(Job).where(*pending_query(profile)).order_by(Job.id.desc()).limit(limit)))


def run_search(profile_id: int, origem: str = "agenda", force: bool = False) -> int | None:
    """Roda uma execução para um perfil. Retorna o id do Run, ou None se outra já estiver
    rodando/for cedo demais. Uma execução por vez no app todo (mantém o volume de busca baixo)."""
    if not _lock.acquire(blocking=False):
        return None
    try:
        s = get_settings()
        with Session(engine) as session:
            profile = session.get(Profile, profile_id)
            if not profile:
                return None
            sch = get_schedule(session, profile)
            if (
                not force
                and sch.ultima_execucao
                and sch.ultima_execucao > now() - timedelta(minutes=s.min_minutes_between_runs)
            ):
                return None
            run = Run(profile_id=profile.id, origem=origem)
            session.add(run)
            sch.ultima_execucao = now()
            session.add(sch)
            session.commit()
            session.refresh(run)
            lines: list[str] = []
            try:
                novas, encontradas, buscas, cursor = collector.collect(
                    session, load_filters(profile), sch.cursor, lines, profile_id=profile.id
                )
                sch.cursor = cursor
                run.buscas, run.encontradas, run.novas = buscas, encontradas, len(novas)
                session.add_all([sch, run])
                session.commit()
                run.analisadas = analyze_pending(session, profile, lines)
                run.status = "ok"
            except Exception as e:
                log.exception("Execução falhou")
                lines.append(f"ERRO: {e}")
                run.status = "erro"
            run.terminado_em = now()
            run.log = "\n".join(lines)[-20000:]
            session.add(run)
            session.commit()
            return run.id
    finally:
        _lock.release()


def analyze_pending(session: Session, profile: Profile, lines: list[str]) -> int:
    n = 0
    falhas_seguidas = 0
    for job in pending_jobs(session, profile, get_settings().analyze_max_per_run):
        # outra execução (ou o CLI) pode ter analisado essa vaga enquanto esta rodava
        if session.exec(select(Analysis.id).where(Analysis.job_id == job.id, Analysis.profile_id == profile.id)).first():
            continue
        try:
            analyze(session, job, profile)
            n += 1
            falhas_seguidas = 0
        except AIError as e:
            session.rollback()
            falhas_seguidas += 1
            lines.append(f"IA falhou em '{job.cargo}' ({job.empresa}): {e}")
            # IA fora do ar ou sem login: para e tenta de novo na próxima execução
            if falhas_seguidas >= 3:
                lines.append("3 falhas seguidas da IA; o resto fica para a próxima execução")
                break
    lines.append(f"{n} vagas analisadas")
    return n


def is_running() -> bool:
    return _lock.locked()


def run_in_background(profile_id: int, origem: str, force: bool = True) -> bool:
    if is_running():
        return False
    threading.Thread(target=run_search, args=(profile_id, origem, force), daemon=True).start()
    return True
