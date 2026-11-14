"""Operações compartilhadas entre a API web e o servidor MCP."""

import json
from datetime import timedelta

from sqlmodel import Session, func, select

from .models import COLUMNS, Analysis, Card, CardEvent, GeneratedCV, Job, Profile, Run, now
from .pipeline import is_running, pending_query
from .profile import get_schedule, profile_has_job


def _loads(s: str | None):
    try:
        return json.loads(s or "[]")
    except json.JSONDecodeError:
        return []


def latest_analysis(session: Session, job_id: int, profile_id: int) -> Analysis | None:
    return session.exec(
        select(Analysis).where(Analysis.job_id == job_id, Analysis.profile_id == profile_id).order_by(Analysis.id.desc())
    ).first()


def analysis_dict(a: Analysis | None) -> dict | None:
    if not a:
        return None
    return {
        "veredito": a.veredito, "score": a.score, "tag": a.tag, "resumo": a.resumo,
        "motivos": _loads(a.motivos_json), "requisitos": _loads(a.requisitos_json),
        "lacunas": _loads(a.lacunas_json), "alertas": [x for x in _loads(a.alertas_json) if x != "salário a confirmar"],
        "motivos_descarte": _loads(a.filtro_motivos_json), "modelo": a.modelo, "criado_em": a.criado_em,
    }


def job_summary(job: Job) -> dict:
    return {
        "id": job.id, "cargo": job.cargo, "empresa": job.empresa, "local": job.local, "modelo": job.modelo,
        "fonte": job.fonte, "url": job.url, "publicada_em": job.publicada_em,
        "salario_min": job.salario_min, "salario_max": job.salario_max,
        "salario_intervalo": job.salario_intervalo, "moeda": job.moeda,
    }


def board(session: Session, profile: Profile) -> dict:
    rows = session.exec(
        select(Card, Job).join(Job, Job.id == Card.job_id).where(Card.profile_id == profile.id).order_by(Card.posicao)
    ).all()
    analyses = {
        a.job_id: a
        for a in session.exec(select(Analysis).where(Analysis.profile_id == profile.id).order_by(Analysis.id))
    }
    cols = {c: [] for c in COLUMNS}
    for card, job in rows:
        a = analyses.get(job.id)
        alertas = [x for x in _loads(a.alertas_json) if x != "salário a confirmar"] if a else []
        cols.setdefault(card.coluna, []).append({
            "card_id": card.id, "coluna": card.coluna, "posicao": card.posicao, "prazo": card.prazo,
            "tem_notas": bool(card.notas.strip()), **job_summary(job),
            "score": a.score if a else None, "tag": a.tag if a else "",
            "veredito": a.veredito if a else "", "alertas": alertas,
            "motivo_descarte": "; ".join(_loads(a.filtro_motivos_json)) if a else "",
        })
    hoje = now() - timedelta(hours=24)
    novas_hoje = session.exec(
        select(func.count()).select_from(Card).where(
            Card.profile_id == profile.id, Card.coluna != "descartadas", Card.criado_em >= hoje
        )
    ).one()
    last = session.exec(
        select(Run).where(Run.profile_id == profile.id, Run.status != "rodando").order_by(Run.id.desc())
    ).first()
    sch = get_schedule(session, profile)
    na_fila = session.exec(select(func.count()).select_from(Job).where(*pending_query(profile))).one()
    return {
        "colunas": cols,
        "novas_hoje": novas_hoje,
        "na_fila": na_fila,
        "atualizado_em": last.terminado_em if last else None,
        "rodando": is_running(),
        "agenda": {"intervalo_horas": sch.intervalo_horas, "ativo": sch.ativo, "ultima_execucao": sch.ultima_execucao},
    }


def job_detail(session: Session, job_id: int, profile: Profile) -> dict | None:
    job = session.get(Job, job_id)
    if not job or not profile_has_job(session, profile.id, job.id):
        return None
    card = session.exec(select(Card).where(Card.job_id == job.id, Card.profile_id == profile.id)).first()
    eventos = []
    if card:
        eventos = [
            {"de": e.de, "para": e.para, "autor": e.autor, "em": e.criado_em}
            for e in session.exec(select(CardEvent).where(CardEvent.card_id == card.id).order_by(CardEvent.id))
        ]
    cvs = [
        {"id": g.id, "criado_em": g.criado_em, "modelo": g.modelo, "arquivo_base": g.arquivo_base, "nota": g.nota}
        for g in session.exec(
            select(GeneratedCV).where(GeneratedCV.job_id == job.id, GeneratedCV.profile_id == profile.id)
            .order_by(GeneratedCV.id.desc())
        )
    ]
    return {
        **job_summary(job),
        "descricao": job.descricao, "tipo": job.tipo, "termo_busca": job.termo_busca, "visto_em": job.visto_em,
        "analise": analysis_dict(latest_analysis(session, job.id, profile.id)),
        "card": {"id": card.id, "coluna": card.coluna, "notas": card.notas, "prazo": card.prazo} if card else None,
        "historico": eventos,
        "cvs": cvs,
    }


def cv_dict(g: GeneratedCV) -> dict:
    return {
        "id": g.id, "job_id": g.job_id, "cv_md": g.cv_md, "relatorio_md": g.relatorio_md, "diff_md": g.diff_md,
        "veracidade": _loads(g.veracidade_json), "mensagem_recrutador": g.mensagem_recrutador,
        "validacao": _loads(g.validacao_json), "modelo": g.modelo, "criado_em": g.criado_em,
        "arquivo_base": g.arquivo_base, "nota": g.nota,
    }


def update_card(session: Session, card: Card, autor: str, coluna: str | None = None, posicao: float | None = None,
                notas: str | None = None, prazo: str | None = None) -> Card:
    if coluna is not None and coluna not in COLUMNS:
        raise ValueError(f"coluna inválida: {coluna}. Use uma de {COLUMNS}")
    if coluna is not None and coluna != card.coluna:
        session.add(CardEvent(card_id=card.id, de=card.coluna, para=coluna, autor=autor))
        card.coluna = coluna
        card.movido_em = now()
        if posicao is None:
            top = session.exec(
                select(func.min(Card.posicao)).where(Card.profile_id == card.profile_id, Card.coluna == coluna)
            ).first()
            card.posicao = (top or 0) - 1
    if posicao is not None:
        card.posicao = posicao
    if notas is not None:
        card.notas = notas
    if prazo is not None:
        card.prazo = prazo
    session.add(card)
    session.commit()
    session.refresh(card)
    return card
