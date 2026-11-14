"""Filtros eliminatórios em código (passo 1 da skill), antes de gastar IA."""

import re
import unicodedata
from datetime import datetime, timedelta

from .models import Job, now


def norm(t: str | None) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _as_list(v) -> list:
    return v if isinstance(v, list) else []


def is_estagio(job: Job) -> bool:
    t = norm(f"{job.cargo} {job.tipo}")
    return bool(re.search(r"estagi|intern\b|internship", t))


def detect_modelo(title: str, desc: str, is_remote: bool | None, location: str) -> str:
    t = norm(f"{title} {location}")
    d = norm(desc[:4000])
    if re.search(r"hibrid|hybrid", t) or re.search(r"(modelo|regime|formato)[^.\n]{0,25}hibrid|hybrid (work|model)", d):
        return "hibrido"
    if is_remote or re.search(r"remot|home ?office|100% remote|\bremote\b", t):
        return "remoto"
    if re.search(r"(modelo|regime|formato)[^.\n]{0,25}(remot|home office)", d):
        return "remoto"
    if re.search(r"(modelo|regime|formato)[^.\n]{0,25}presencial|\bpresencial\b|on-?site", d):
        return "presencial"
    return ""


def _monthly(job: Job) -> float | None:
    val = job.salario_max or job.salario_min
    if not val:
        return None
    iv = (job.salario_intervalo or "").lower()
    if iv == "yearly":
        return val / 12
    if iv == "hourly":
        return val * 220
    if iv == "weekly":
        return val * 4.33
    if iv == "daily":
        return val * 22
    return val


_NUM = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5}


def _num(s: str) -> int:
    return int(s) if s.isdigit() else _NUM.get(s, 0)


# Palavras genéricas que aparecem em qualquer título e não dizem a área
_GENERICAS = {
    "de", "da", "do", "das", "dos", "em", "e", "a", "o", "para", "com", "and", "of", "the", "in", "to",
    "estagio", "estagiario", "estagiaria", "estagiarios", "intern", "internship", "trainee", "jovem", "aprendiz",
    "analista", "analyst", "assistente", "assistant", "auxiliar", "pessoa", "junior", "jr", "pleno", "senior", "sr",
    "especialista", "specialist", "lead", "coordenador", "gerente", "manager", "vaga", "remoto", "remote", "hibrido",
    "presencial", "i", "ii", "iii", "iv", "area", "time", "nivel", "programa", "talentos", "banco", "gestao",
    "management", "geral", "operacoes", "operations",
}


def title_words(t: str) -> set[str]:
    words = set(re.findall(r"[a-z0-9&+#]+", norm(t)))
    out = set()
    for w in words:
        if w in _GENERICAS or len(w) < 2:
            continue
        out.add(w)
        if len(w) > 4 and w.endswith("s"):  # plural simples: dados -> dado
            out.add(w[:-1])
    return out


def area_vocab(filtros: dict) -> set[str]:
    vocab: set[str] = set()
    for c in _as_list(filtros.get("cargos")):
        if not isinstance(c, dict):
            continue
        vocab |= title_words(str(c.get("area", "")))
        for t in _as_list(c.get("titulos")):
            vocab |= title_words(str(t))
    if vocab & {"dados", "dado", "data", "bi", "analytics", "analytic"}:
        vocab |= _DADOS_AFINS
    return vocab


# Títulos afins quando a pessoa busca dados (IA, estatística, inteligência de mercado, métricas...)
_DADOS_AFINS = {
    "ia", "ai", "inteligencia", "artificial", "llm", "genai", "estatistica", "estatistico", "statistics",
    "statistical", "quantitativo", "quantitativa", "quant", "modelagem", "modeling", "sql", "dashboard",
    "dashboards", "insights", "metricas", "metrics", "kpi", "reporting", "automacao", "automation", "growth", "crm",
}


def check(job: Job, filtros: dict) -> dict:
    """Retorna {veredito: APROVADA|ALERTA|DESCARTADA, motivos: [...], alertas: [...]}."""
    motivos: list[str] = []
    alertas: list[str] = []
    title = norm(job.cargo)
    desc = norm(job.descricao)

    for w in _as_list(filtros.get("excluir_titulos")):
        if re.search(rf"(?<![a-z]){re.escape(norm(w))}(?![a-z])", title):
            motivos.append(f"título contém '{w}'")
            break

    # Senioridade implícita (PL, III, IV...) quando o perfil não busca pleno/sênior
    niveis = {norm(str(n)) for n in _as_list(filtros.get("nivel"))}
    if niveis and not niveis & {"pleno", "senior", "especialista"} and not motivos:
        m = re.search(r"(?<![a-z])(pl|pleno|sr|senior|iii|iv|lead|staff|principal|especialista)(?![a-z])", title)
        if m:
            motivos.append(f"senioridade acima do perfil ('{m.group(1)}' no título)")

    # Título fora das áreas de busca (o LinkedIn devolve resultados soltos): descarta antes de gastar IA
    if filtros.get("filtrar_titulo_fora_da_area", True) is not False and not motivos and job.fonte != "manual":
        vocab = area_vocab(filtros)
        if vocab and not (title_words(job.cargo) & vocab):
            motivos.append("título fora das áreas de busca")

    for w in _as_list(filtros.get("palavras_excluir")):
        if norm(w) and (norm(w) in title or norm(w) in desc):
            motivos.append(f"contém '{w}'")
            break

    emp = norm(job.empresa)
    for b in _as_list(filtros.get("empresas_bloqueadas")):
        if norm(b) and norm(b) in emp:
            motivos.append(f"empresa bloqueada ({b})")

    dias = filtros.get("publicada_ha_no_maximo_dias")
    if isinstance(dias, (int, float)) and job.publicada_em and job.publicada_em < now() - timedelta(days=dias + 1):
        motivos.append(f"publicada há mais de {dias} dias")

    # Modelo de trabalho e cidade
    mt = filtros.get("modelo_trabalho") or {}
    modelo = job.modelo
    if modelo and isinstance(mt, dict) and modelo in mt:
        conf = mt.get(modelo) or {}
        if isinstance(conf, dict) and conf.get("aceita") is False:
            motivos.append(f"modelo {modelo} não aceito")
        elif modelo in ("hibrido", "presencial") and isinstance(conf, dict):
            cidades = _as_list(conf.get("cidades"))
            loc = norm(job.local)
            if cidades and loc:
                ok = any(norm(c.split("-")[0].split(",")[0].strip()) in loc for c in cidades)
                if not ok:
                    motivos.append(f"{modelo} fora de {', '.join(cidades)} ({job.local})")

    # Remuneração
    rem = filtros.get("remuneracao") or {}
    mensal = _monthly(job)
    if mensal and (job.moeda or "BRL").upper() in ("BRL", "R$", ""):
        if is_estagio(job):
            minimo = (rem.get("estagio") or {}).get("minimo_bolsa")
        else:
            minimo = (rem.get("clt") or {}).get("minimo_base")
        if isinstance(minimo, (int, float)) and mensal < minimo:
            motivos.append(f"salário R$ {mensal:,.0f}/mês abaixo do mínimo R$ {minimo:,.0f}".replace(",", "."))
    elif not mensal and rem.get("nao_informado") == "descartar":
        motivos.append("salário não informado")
    elif not mensal:
        alertas.append("salário a confirmar")

    restr = filtros.get("restricoes_eliminatorias") or {}

    # Disponibilidade de estágio (bloqueio revisável → alerta)
    max_meses = restr.get("disponibilidade_estagio_max_meses")
    if is_estagio(job) and isinstance(max_meses, (int, float)):
        pat = (
            r"(?:disponibilidade|duracao|programa|contrato|periodo|permanencia|minimo de)[^.\n]{0,60}?"
            r"(\d+|um|uma|dois|duas|tres)\s*(anos?|meses)"
        )
        exigido = 0
        for m in re.finditer(pat, desc):
            n = _num(m.group(1))
            exigido = max(exigido, n * 12 if m.group(2).startswith("ano") else n)
        for m in re.finditer(r"(\d+|um|uma|dois|duas|tres)\s*(anos?|meses)\s*(?:de|do)\s*(?:programa|estagio|contrato)", desc):
            n = _num(m.group(1))
            exigido = max(exigido, n * 12 if m.group(2).startswith("ano") else n)
        if exigido > max_meses:
            alertas.append(f"estágio pede {exigido} meses de disponibilidade; o limite é ~{int(max_meses)} meses (formatura)")

    # Anos de experiência
    max_exp = restr.get("anos_experiencia_max")
    if isinstance(max_exp, (int, float)):
        exp = 0
        for m in re.finditer(r"(\d+)\+?\s*(?:anos?|years?)\s*(?:de|of)\s*(?:experiencia|experience)", desc):
            exp = max(exp, int(m.group(1)))
        if exp > max_exp + 1:
            motivos.append(f"pede {exp} anos de experiência")
        elif exp > max_exp:
            alertas.append(f"pede {exp} anos de experiência")

    # Inglês
    ing = norm(str(filtros.get("ingles_maximo_exigido", "")))
    if ing in ("basico", "intermediario"):
        if re.search(r"ingles\s*(fluente|avancado|c1|c2)|(fluent|advanced)\s*english|english\s*(fluency|c1|c2)|fluency in english", desc):
            alertas.append("vaga pede inglês fluente/avançado")

    if motivos:
        return {"veredito": "DESCARTADA", "motivos": motivos, "alertas": alertas}
    real_alerts = [a for a in alertas if a != "salário a confirmar"]
    return {"veredito": "ALERTA" if real_alerts else "APROVADA", "motivos": [], "alertas": alertas}


def tag_for(score: int | None) -> str:
    if score is None:
        return ""
    if score >= 80:
        return "quente"
    if score >= 65:
        return "morna"
    if score >= 50:
        return "fria"
    return ""


def parse_date(v) -> datetime | None:
    if v is None:
        return None
    try:
        import pandas as pd

        if pd.isna(v):
            return None
        ts = pd.Timestamp(v)
        ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        return ts.to_pydatetime()
    except Exception:
        return None
