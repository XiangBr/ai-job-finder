"""Geração do CV adaptado com validação de veracidade e export DOCX/PDF."""

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

from sqlmodel import Session

from .ai.providers import get_provider
from pydantic import BaseModel, ConfigDict, Field

from .ai.schemas import CVAdaptado, Veracidade
from .config import get_settings
from .filters import norm
from .models import Analysis, GeneratedCV, Job, Profile
from .profile import load_facts

log = logging.getLogger(__name__)
NL = chr(10)  # quebra de linha


# ------------------------------------------------------------------ validação

def fact_ids(fatos: dict) -> set[str]:
    ids: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            if "id" in node:
                ids.add(str(node["id"]))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(fatos)
    return ids


def _numbers(text: str) -> list[str]:
    text = re.sub(r"\[\[.*?\]\]", " ", text)  # marcadores de pendência não contam
    return re.findall(r"\d+(?:[.,]\d+)?", text)


def _key(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", norm(re.sub(r"\*\*|__|`", "", t))).strip()


def cv_bullets(cv_md: str) -> list[str]:
    return [ln.strip()[2:].strip() for ln in cv_md.splitlines() if re.match(r"\s*[-*] ", ln)]


def validate(cv: CVAdaptado, fatos_yaml: str, fatos: dict) -> list[dict]:
    return validate_md(cv.cv_md, cv.veracidade, fatos_yaml, fatos)


def validate_md(cv_md: str, veracidade, fatos_yaml: str, fatos: dict) -> list[dict]:
    """Regra 1 do AGENTS.md: todo bullet aponta para IDs válidos; nenhum número fora dos fatos."""
    ids = fact_ids(fatos)
    fatos_nums = set(_numbers(fatos_yaml))
    ver = {_key(v.bullet): v for v in veracidade}
    problemas = []
    for b in cv_bullets(cv_md):
        k = _key(b)
        v = ver.get(k) or next((x for kk, x in ver.items() if kk and (kk in k or k in kk)), None)
        if not v or not v.fatos_ids:
            problemas.append({"bullet": b, "motivo": "bullet sem ID de fato"})
            continue
        bad = [i for i in v.fatos_ids if i not in ids]
        if bad:
            problemas.append({"bullet": b, "motivo": f"ID inexistente: {', '.join(bad)}"})
            continue
        extra = [n for n in _numbers(b) if n not in fatos_nums and n.replace(",", ".") not in fatos_nums]
        if extra:
            problemas.append({"bullet": b, "motivo": f"número fora dos fatos: {', '.join(extra)}"})
    return problemas


def strip_bullets(cv_md: str, bullets: list[str]) -> str:
    drop = {_key(b) for b in bullets}
    out = [ln for ln in cv_md.splitlines() if not (re.match(r"\s*[-*] ", ln) and _key(ln.strip()[2:]) in drop)]
    return "\n".join(out)


# ------------------------------------------------------------------ geração

def _slug(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", norm(t)).strip("_")[:40] or "x"


def report_md(cv: CVAdaptado, analise: Analysis | None, problemas: list[dict]) -> str:
    L = [f"# Relatório — {cv.titulo_alvo}", ""]
    if analise:
        L += [f"**Veredito:** {analise.veredito} · **Score:** {analise.score} · **Tag:** {analise.tag or '-'}", ""]
    L += [f"**Fio narrativo:** {cv.fio_narrativo}", "", f"**Cobertura de palavras-chave:** {cv.cobertura_palavras_chave}", ""]
    L += ["## Tabela de veracidade", "", "| Bullet | Fatos |", "| --- | --- |"]
    L += [f"| {v.bullet.replace('|', '/')} | {', '.join(v.fatos_ids) or '—'} |" for v in cv.veracidade]
    L += ["", "## O que mudou contra o CV base", ""] + [f"- {d}" for d in cv.diff]
    L += ["", "## Lacunas e como tratar", ""] + [f"- **{x.lacuna}:** {x.como_tratar}" for x in cv.lacunas]
    L += ["", "## Mensagem ao recrutador", "", cv.mensagem_recrutador]
    L += ["", "## Perguntas prováveis de entrevista", ""]
    for p in cv.perguntas_entrevista:
        L += [f"**{p.pergunta}**", "", p.roteiro_star, ""]
    if problemas:
        L += ["", "## Bullets removidos pelo validador", ""] + [f"- {p['bullet']} — {p['motivo']}" for p in problemas]
    return "\n".join(L)


def tailor(session: Session, job: Job, profile: Profile, analise: Analysis | None) -> GeneratedCV:
    fatos = load_facts(profile)
    pre = None
    if analise and analise.modelo != "filtro":
        pre = {
            "score": analise.score, "veredito": analise.veredito, "motivos": json.loads(analise.motivos_json),
            "requisitos": json.loads(analise.requisitos_json), "lacunas": json.loads(analise.lacunas_json),
        }
    provider = get_provider()
    regras = profile.regras_cv
    cv, modelo = provider.tailor_cv(job, profile.fatos_yaml, profile.cv_base_md, pre, regras=regras)
    problemas = validate(cv, profile.fatos_yaml, fatos)
    if problemas and provider.name != "mock":
        feedback = "\n".join(f"- {p['bullet']}: {p['motivo']}" for p in problemas)
        cv, modelo = provider.tailor_cv(job, profile.fatos_yaml, profile.cv_base_md, pre, feedback, regras)
        problemas = validate(cv, profile.fatos_yaml, fatos)
    cv_md = strip_bullets(cv.cv_md, [p["bullet"] for p in problemas]) if problemas else cv.cv_md

    nome = (fatos.get("candidato") or {}).get("nome") or profile.nome
    base = f"{_slug(nome)}_{_slug(cv.titulo_alvo or job.cargo)}_{_slug(job.empresa)}"
    g = GeneratedCV(
        job_id=job.id, profile_id=profile.id, cv_md=cv_md,
        relatorio_md=report_md(cv, analise, problemas),
        diff_md="\n".join(f"- {d}" for d in cv.diff),
        veracidade_json=json.dumps([v.model_dump() for v in cv.veracidade], ensure_ascii=False),
        mensagem_recrutador=cv.mensagem_recrutador,
        validacao_json=json.dumps(problemas, ensure_ascii=False),
        arquivo_base=base, modelo=modelo, nota="gerado",
    )
    session.add(g)
    session.commit()
    session.refresh(g)
    try:
        export_docx(g)
    except Exception:
        log.exception("Falha ao gerar DOCX")
    return g


# ------------------------------------------------------------------ ajuste por vaga (chat)

class CVEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resposta: str = Field(description="Resposta curta à pessoa: o que fez ou por que não fez")
    cv_md: str = Field(description="CV completo ajustado (igual ao atual se não mudou)")
    veracidade: list[Veracidade] = Field(description="Uma linha por bullet do cv_md, com os IDs de fatos")
    mudancas: list[str] = Field(description="O que mudou, uma linha por mudança")


EDIT_SYSTEM = """Você ajusta, a pedido da pessoa candidata, um CV que já foi adaptado para uma vaga específica no app AI-JOB-FINDER.

Você recebe a vaga, o fatos.yaml, as regras de escrita da pessoa (se houver), o CV atual (markdown) e a mensagem.
Devolva o CV COMPLETO ajustado, aplicando só o que foi pedido. O resto fica igual.

Regras invioláveis (o backend valida e remove o que não passar):
- Nada inventado: nenhum número, ferramenta, cargo, certificação ou resultado fora do fatos.yaml. Não suba nível ("participei" não vira "liderei"). Se o pedido exigir isso, não aplique; explique na 'resposta' e sugira informar o fato na aba Currículo.
- 'veracidade': uma linha por bullet do cv_md, com o texto exato do bullet e os IDs de fatos que o sustentam.
- Formato: '# Nome', linha de contatos, '## Seção', '### Cargo | Empresa | período', bullets com '- '. Coluna única, sem tabelas, ícones ou imagens.
- O pedido da mensagem vale para este CV mesmo que contrarie as regras gerais da pessoa.

Use a skill abaixo como referência de boas práticas, exceto onde a pessoa pediu diferente.

=== SKILL cv-adaptar-vaga ===
"""


def edit(session: Session, g: GeneratedCV, job: Job, profile: Profile, mensagem: str, historico: list[dict]) -> dict:
    """Aplica um pedido de ajuste. Se o CV mudar, cria uma nova versão (as anteriores ficam guardadas)."""
    from .ai.prompts import job_block, regras_block, skill_text

    s = get_settings()
    provider = get_provider()
    if provider.name == "mock":
        return {"resposta": "(mock) sem IA configurada; nada foi alterado.", "mudancas": [], "validacao": [], "cv": None}
    fatos = load_facts(profile)
    hist = NL.join(f"{m.get('role', 'user')}: {m.get('text', '')}" for m in historico[-8:])
    parts = [
        f"<vaga>{NL}{job_block(job)}{NL}</vaga>",
        f"<fatos_yaml>{NL}{profile.fatos_yaml}{NL}</fatos_yaml>",
        regras_block(profile.regras_cv),
        f"<cv_atual>{NL}{g.cv_md}{NL}</cv_atual>",
        f"<conversa_anterior>{NL}{hist}{NL}</conversa_anterior>" if hist else "",
        f"<mensagem>{NL}{mensagem}{NL}</mensagem>",
    ]
    out = provider.structured(EDIT_SYSTEM + skill_text("cv-adaptar-vaga"), (NL * 2).join(p for p in parts if p),
                              CVEdit, s.ai_model_cv, "low")
    if out.cv_md.strip() == g.cv_md.strip():
        return {"resposta": out.resposta, "mudancas": out.mudancas, "validacao": [], "cv": None}
    problemas = validate_md(out.cv_md, out.veracidade, profile.fatos_yaml, fatos)
    cv_md = strip_bullets(out.cv_md, [p["bullet"] for p in problemas]) if problemas else out.cv_md
    nota = " ".join(mensagem.split())[:120]
    ajuste = NL.join(["", "", f"## Ajuste: {nota}", ""] + [f"- {m}" for m in out.mudancas])
    novo = GeneratedCV(
        job_id=g.job_id, profile_id=g.profile_id, cv_md=cv_md,
        relatorio_md=g.relatorio_md + ajuste,
        diff_md=g.diff_md, mensagem_recrutador=g.mensagem_recrutador,
        veracidade_json=json.dumps([v.model_dump() for v in out.veracidade], ensure_ascii=False),
        validacao_json=json.dumps(problemas, ensure_ascii=False),
        arquivo_base=g.arquivo_base, modelo=f"{provider.name}:{s.ai_model_cv}", nota=nota,
    )
    session.add(novo)
    session.commit()
    session.refresh(novo)
    try:
        export_docx(novo)
    except Exception:
        log.exception("Falha ao gerar DOCX")
    return {"resposta": out.resposta, "mudancas": out.mudancas, "validacao": problemas, "cv": novo}


# ------------------------------------------------------------------ export

def _paths(g: GeneratedCV) -> tuple[Path, Path]:
    d = get_settings().cv_dir / str(g.id)
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{g.arquivo_base}.docx", d / f"{g.arquivo_base}.pdf"


def _add_runs(par, text: str):
    for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        if not part:
            continue
        if i % 2 == 1:
            par.add_run(part).bold = True
            continue
        for j, sub in enumerate(re.split(r"(?<![*\w])[*_](.+?)[*_](?![*\w])", part)):
            if sub:
                par.add_run(sub).italic = j % 2 == 1


def export_docx(g: GeneratedCV) -> Path:
    from docx import Document
    from docx.shared import Pt

    docx_path, _ = _paths(g)
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = Pt(50)
    for ln in g.cv_md.splitlines():
        s = ln.rstrip()
        if not s.strip():
            continue
        if s.startswith("# "):
            doc.add_heading(s[2:].strip(), level=0)
        elif s.startswith("## "):
            doc.add_heading(s[3:].strip(), level=1)
        elif s.startswith("### "):
            doc.add_heading(s[4:].strip(), level=2)
        elif re.match(r"\s*[-*] ", s):
            _add_runs(doc.add_paragraph(style="List Bullet"), s.strip()[2:])
        else:
            _add_runs(doc.add_paragraph(), s.strip())
    doc.save(docx_path)
    return docx_path


def get_file(g: GeneratedCV, fmt: str) -> Path | None:
    docx_path, pdf_path = _paths(g)
    if not docx_path.exists():
        export_docx(g)
    if fmt == "docx":
        return docx_path
    if pdf_path.exists():
        return pdf_path
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(pdf_path.parent), str(docx_path)],
        capture_output=True, timeout=120,
    )
    return pdf_path if pdf_path.exists() else None
