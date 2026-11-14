import logging
from pathlib import Path

import yaml
from sqlmodel import Session, select

from .config import ROOT, get_settings
from .models import Job, Profile, ProfileJob, Schedule, User

log = logging.getLogger(__name__)


def get_profile(session: Session, user: User) -> Profile:
    """Perfil do usuário logado. Cada usuário tem o seu (CV, fatos, filtros, kanban e agenda)."""
    p = session.exec(select(Profile).where(Profile.user_id == user.id).order_by(Profile.id)).first()
    if not p:
        p = Profile(nome=user.username, user_id=user.id)
        session.add(p)
        session.commit()
        session.refresh(p)
    return p


def all_profiles(session: Session) -> list[Profile]:
    return list(session.exec(select(Profile).where(Profile.user_id.is_not(None)).order_by(Profile.id)))


def mcp_profile(session: Session) -> Profile:
    """Perfil usado pelo servidor MCP: o do usuário MCP_USER, ou o do primeiro usuário."""
    name = get_settings().mcp_user.strip()
    q = select(User).where(User.username == name) if name else select(User).order_by(User.id)
    user = session.exec(q).first()
    if not user:
        raise RuntimeError("nenhum usuário cadastrado")
    return get_profile(session, user)


def link_job(session: Session, profile_id: int, job_id: int) -> bool:
    """Marca que a vaga foi encontrada para o perfil. Retorna True se o vínculo é novo (não faz commit)."""
    exists = session.exec(
        select(ProfileJob.id).where(ProfileJob.profile_id == profile_id, ProfileJob.job_id == job_id)
    ).first()
    if exists:
        return False
    session.add(ProfileJob(profile_id=profile_id, job_id=job_id))
    return True


def profile_has_job(session: Session, profile_id: int, job_id: int) -> bool:
    return bool(session.exec(
        select(ProfileJob.id).where(ProfileJob.profile_id == profile_id, ProfileJob.job_id == job_id)
    ).first())


def migrate_profiles(session: Session) -> None:
    """Bancos da versão de perfil único: o perfil sem dono vai para LEGACY_PROFILE_OWNER (ou o
    primeiro usuário), e todas as vagas já coletadas ficam ligadas a ele. Idempotente."""
    orphans = list(session.exec(select(Profile).where(Profile.user_id.is_(None)).order_by(Profile.id)))
    if not orphans:
        return
    name = get_settings().legacy_profile_owner.strip()
    q = select(User).where(User.username == name) if name else select(User).order_by(User.id)
    owner = session.exec(q).first()
    if not owner:
        return  # sem usuários ainda; tenta de novo no próximo boot
    if session.exec(select(Profile).where(Profile.user_id == owner.id)).first():
        log.warning("Perfil sem dono %s ignorado: %s já tem perfil", [p.id for p in orphans], owner.username)
        return
    legacy = orphans[0]
    legacy.user_id = owner.id
    session.add(legacy)
    if not session.exec(select(ProfileJob.id)).first():
        for job_id in session.exec(select(Job.id)).all():
            session.add(ProfileJob(profile_id=legacy.id, job_id=job_id))
    session.commit()
    _move_legacy_uploads(legacy.id)
    log.info("Perfil %s (%s) agora pertence a %s", legacy.id, legacy.nome, owner.username)


def _move_legacy_uploads(profile_id: int) -> None:
    d = get_settings().data_dir / "uploads"
    if not (d / "cv_original.json").exists():
        return
    dest = d / str(profile_id)
    dest.mkdir(parents=True, exist_ok=True)
    for f in d.glob("cv_original.*"):
        f.rename(dest / f.name)


def get_schedule(session: Session, profile: Profile) -> Schedule:
    sch = session.exec(select(Schedule).where(Schedule.profile_id == profile.id)).first()
    if not sch:
        horas = _parse_freq(load_filters(profile).get("frequencia_alerta"))
        sch = Schedule(profile_id=profile.id, intervalo_horas=horas)
        session.add(sch)
        session.commit()
        session.refresh(sch)
    return sch


def _parse_freq(v) -> float:
    import re

    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*h", str(v or ""))
    return float(m.group(1).replace(",", ".")) if m else 6.0


def load_yaml(text: str) -> dict:
    try:
        data = yaml.safe_load(text or "") or {}
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def load_filters(profile: Profile) -> dict:
    data = load_yaml(profile.filtros_yaml)
    return data.get("perfil_busca", data)


def load_facts(profile: Profile) -> dict:
    return load_yaml(profile.fatos_yaml)


def seed_profile(session: Session) -> None:
    """Na primeira vez, carrega fatos/filtros/CV base da pasta SEED_PROFILE_DIR para o primeiro usuário."""
    s = get_settings()
    if session.exec(select(Profile)).first() or not s.seed_profile_dir:
        return
    owner = session.exec(select(User).order_by(User.id)).first()
    if not owner:
        return
    d = Path(s.seed_profile_dir)
    if not d.is_absolute():
        d = ROOT / d
    if not d.is_dir():
        log.warning("SEED_PROFILE_DIR não existe: %s", d)
        return
    cv = next(iter(sorted(d.glob("*cv_base*.md")) + sorted(d.glob("*CV_base*.md"))), None)
    p = Profile(
        user_id=owner.id,
        nome=s.seed_profile_name,
        fatos_yaml=(d / "fatos.yaml").read_text(encoding="utf-8") if (d / "fatos.yaml").exists() else "",
        filtros_yaml=(d / "filtros.yaml").read_text(encoding="utf-8") if (d / "filtros.yaml").exists() else "",
        cv_base_md=cv.read_text(encoding="utf-8") if cv else "",
    )
    session.add(p)
    session.commit()
    log.info("Perfil inicial carregado de %s", d)
