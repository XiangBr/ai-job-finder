"""Coleta de vagas com JobSpy (sem IA). Volume baixo e rodízio entre buscas."""

import hashlib
import json
import logging
import random
import time

from sqlmodel import Session, select

from .config import get_settings
from .filters import detect_modelo, norm, parse_date
from .models import Job

log = logging.getLogger(__name__)

SITE_MAP = {
    "linkedin": "linkedin", "linkedin_guest": "linkedin",
    "indeed": "indeed", "glassdoor": "glassdoor", "google": "google",
}


def job_hash(empresa: str, cargo: str, local: str) -> str:
    """Hash empresa + cargo + cidade (só a 1ª parte do local, para casar LinkedIn e Indeed)."""
    import re

    cidade = (local or "").split(",")[0]
    key = "|".join(re.sub(r"[^a-z0-9]+", " ", norm(x)).strip() for x in (empresa, cargo, cidade))
    return hashlib.sha1(key.encode()).hexdigest()


_GENERO = [
    (r"\bestagi(ari[oa]|o)\b", "estagio"),
    (r"\bengenheir[oa]\b", "engenheiro"),
    (r"\bdesenvolvedora?\b", "desenvolvedor"),
    (r"\bcientista\b", "cientista"),
    (r"\banalista\b", "analista"),
]


def _title_key(t: str) -> str:
    """Chave para juntar variações de gênero ('Estagiária em X' = 'Estágio em X'): o LinkedIn já busca por aproximação."""
    import re

    k = re.sub(r"[^a-z0-9 ]+", " ", norm(t))
    for pat, rep in _GENERO:
        k = re.sub(pat, rep, k)
    return " ".join(k.split())


def search_titles(filtros: dict) -> list[str]:
    """Títulos de busca intercalando as áreas (1º título de cada área, depois o 2º...), sem variações de gênero repetidas.
    Assim cada execução cobre todas as áreas, com as de maior prioridade primeiro."""
    cargos = sorted(
        [c for c in filtros.get("cargos", []) if isinstance(c, dict)],
        key=lambda c: c.get("prioridade", 99),
    )
    listas = [[t for t in (c.get("titulos") or []) if isinstance(t, str) and t.strip()] for c in cargos]
    titulos: list[str] = []
    vistos: set[str] = set()
    for i in range(max((len(x) for x in listas), default=0)):
        for lst in listas:
            if i < len(lst) and _title_key(lst[i]) not in vistos:
                vistos.add(_title_key(lst[i]))
                titulos.append(lst[i])
    return titulos


def build_plan(filtros: dict) -> list[dict]:
    """Uma busca por título x local, com as áreas intercaladas."""
    titulos = search_titles(filtros)

    mt = filtros.get("modelo_trabalho") or {}
    locais: list[dict] = []
    if (mt.get("remoto") or {}).get("aceita", True):
        locais.append({"location": "Brazil", "is_remote": True})
    cidades: list[str] = []
    for k in ("hibrido", "presencial"):
        conf = mt.get(k) or {}
        if conf.get("aceita"):
            for c in conf.get("cidades", []) or []:
                if c not in cidades:
                    cidades.append(c)
    for c in cidades:
        locais.append({"location": c.replace(" - ", ", "), "is_remote": False})
    if not locais:
        locais.append({"location": "Brazil", "is_remote": False})

    sites = []
    for f in filtros.get("fontes") or ["linkedin", "indeed"]:
        s = SITE_MAP.get(str(f).lower())
        if s and s not in sites:
            sites.append(s)
    sites = sites or ["linkedin", "indeed"]

    dias = filtros.get("publicada_ha_no_maximo_dias") or 7
    return [
        {"search_term": t, **loc, "sites": sites, "hours_old": int(dias) * 24}
        for t in titulos
        for loc in locais
    ]


def _str(v) -> str:
    try:
        import pandas as pd

        if v is None or (not isinstance(v, (list, dict)) and pd.isna(v)):
            return ""
    except (TypeError, ValueError):
        pass
    return str(v)


def _num(v) -> float | None:
    try:
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def scrape(search: dict) -> list[dict]:
    from jobspy import scrape_jobs

    s = get_settings()
    proxies = [p.strip() for p in s.jobspy_proxies.split(",") if p.strip()] or None
    df = scrape_jobs(
        site_name=search["sites"],
        search_term=search["search_term"],
        location=search["location"],
        is_remote=search["is_remote"],
        hours_old=search["hours_old"],
        results_wanted=s.results_per_search,
        country_indeed="Brazil",
        linkedin_fetch_description=True,
        description_format="markdown",
        proxies=proxies,
        verbose=0,
    )
    if df is None or df.empty:
        return []
    return df.to_dict(orient="records")


def row_to_job(row: dict, termo: str, busca_remota: bool = False) -> Job:
    cargo = _str(row.get("title"))
    empresa = _str(row.get("company"))
    local = _str(row.get("location"))
    desc = _str(row.get("description"))
    is_remote = row.get("is_remote")
    is_remote = bool(is_remote) if isinstance(is_remote, bool) else None
    raw = {k: _str(v) for k, v in row.items() if k not in ("description",)}
    return Job(
        hash=job_hash(empresa, cargo, local),
        fonte=_str(row.get("site")),
        url=_str(row.get("job_url_direct")) or _str(row.get("job_url")),
        cargo=cargo,
        empresa=empresa,
        local=local,
        remoto=is_remote,
        modelo=detect_modelo(cargo, desc, is_remote, local) or ("remoto" if busca_remota else ""),
        tipo=_str(row.get("job_type")),
        salario_min=_num(row.get("min_amount")),
        salario_max=_num(row.get("max_amount")),
        salario_intervalo=_str(row.get("interval")),
        moeda=_str(row.get("currency")),
        publicada_em=parse_date(row.get("date_posted")),
        descricao=desc,
        termo_busca=termo,
        raw_json=json.dumps(raw, ensure_ascii=False)[:20000],
    )


def save_new(session: Session, jobs: list[Job], profile_id: int | None = None) -> list[Job]:
    """Deduplica por URL e por hash empresa+cargo+local. Com profile_id, liga ao perfil tanto as
    vagas novas quanto as que já existiam no banco (achadas antes por outro perfil).
    Retorna as vagas novas para o perfil."""
    from .profile import link_job

    novos: list[Job] = []
    for j in jobs:
        if not j.cargo or not j.url:
            continue
        if any(n.hash == j.hash or n.url == j.url for n in novos):
            continue
        existing = session.exec(select(Job).where((Job.hash == j.hash) | (Job.url == j.url))).first()
        if existing:
            if profile_id is not None and link_job(session, profile_id, existing.id):
                novos.append(existing)
            continue
        session.add(j)
        session.flush()
        if profile_id is not None:
            link_job(session, profile_id, j.id)
        novos.append(j)
    session.commit()
    for j in novos:
        session.refresh(j)
    return novos


def collect(session: Session, filtros: dict, cursor: int, log_lines: list[str],
            profile_id: int | None = None) -> tuple[list[Job], int, int, int]:
    """Roda até max_searches_per_run buscas a partir do cursor. Retorna (novas, encontradas, buscas, novo_cursor)."""
    s = get_settings()
    plan = build_plan(filtros)
    if not plan:
        log_lines.append("Nenhum título em filtros.yaml")
        return [], 0, 0, cursor
    n = min(s.max_searches_per_run, len(plan))
    encontradas = 0
    novas: list[Job] = []
    for i in range(n):
        search = plan[(cursor + i) % len(plan)]
        label = f"'{search['search_term']}' em {search['location']}{' (remoto)' if search['is_remote'] else ''}"
        try:
            rows = scrape(search)
        except Exception as e:  # JobSpy levanta vários tipos (429, parsing...)
            log_lines.append(f"ERRO {label}: {str(e)[:200]}")
            log.warning("Busca falhou %s: %s", label, e)
            rows = []
        jobs = [row_to_job(r, search["search_term"], search["is_remote"]) for r in rows]
        encontradas += len(jobs)
        saved = save_new(session, jobs, profile_id)
        novas.extend(saved)
        log_lines.append(f"{label}: {len(jobs)} encontradas, {len(saved)} novas")
        if i < n - 1:
            time.sleep(s.min_seconds_between_searches + random.uniform(0, 3))
    return novas, encontradas, n, (cursor + n) % len(plan)
