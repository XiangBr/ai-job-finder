"""Agendamento com APScheduler. A frequência fica no banco e é editável pela tela."""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session

from .db import engine
from .models import now
from .pipeline import run_search
from .profile import all_profiles, get_schedule

log = logging.getLogger(__name__)
_sched = BackgroundScheduler(timezone="UTC")


def _tick():
    """Roda a cada 5 min e dispara a busca de cada perfil cujo intervalo já passou (um por vez)."""
    with Session(engine) as s:
        due = []
        for p in all_profiles(s):
            if not p.filtros_yaml.strip():
                continue
            sch = get_schedule(s, p)
            if sch.ativo and (
                sch.ultima_execucao is None or sch.ultima_execucao + timedelta(hours=sch.intervalo_horas) <= now()
            ):
                due.append(p.id)
    for profile_id in due:
        log.info("Busca agendada disparada (perfil %s)", profile_id)
        run_search(profile_id, "agenda", force=True)


def start():
    if not _sched.running:
        _sched.add_job(
            _tick, "interval", minutes=5, id="tick", max_instances=1, coalesce=True,
            next_run_time=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
        _sched.start()


def stop():
    if _sched.running:
        _sched.shutdown(wait=False)
