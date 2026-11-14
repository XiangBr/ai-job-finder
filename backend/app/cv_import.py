"""Upload do currículo (PDF, DOCX, DOC/ODT/RTF): extrai o texto e a IA monta fatos.yaml + CV base."""

import io
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .ai.prompts import skill_text
from .config import get_settings

ALLOWED = {".pdf", ".docx", ".doc", ".odt", ".rtf", ".txt", ".md"}
MAX_BYTES = 10 * 1024 * 1024


class ImportError_(RuntimeError):
    pass


# ------------------------------------------------------------------ extração

def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:
        raise ImportError_(f"Não consegui ler o PDF: {e}")


BULLET_RE = re.compile(r"^\s*[•●▪◦■□➢➤►\-–*·]\s+")


def _para_md(p, first: bool) -> str:
    """Um parágrafo do Word em markdown, sem mudar o texto: só marca título, lista e negrito."""
    text = p.text.strip()
    if not text:
        return ""
    style = (p.style.name if p.style is not None else "").lower()
    if style in ("title", "título") or (first and len(text) < 60):
        return f"# {text}"
    m = re.search(r"(heading|título)\s*(\d)", style)
    if m:
        return f"{'#' * min(int(m.group(2)) + 1, 4)} {text}"
    ppr = p._p.pPr
    is_list = "list" in style or "lista" in style or (ppr is not None and ppr.numPr is not None)
    if is_list or BULLET_RE.match(text):
        return f"- {BULLET_RE.sub('', text)}"
    runs = [r for r in p.runs if r.text.strip()]
    if text.isupper() and len(text) < 50:
        return f"## {text}"
    if runs and all(r.bold for r in runs) and len(text) < 90:
        return f"### {text}"
    return text


def _docx_text(data: bytes) -> str:
    from docx import Document

    try:
        doc = Document(io.BytesIO(data))
    except Exception as e:
        raise ImportError_(f"Não consegui ler o DOCX: {e}")
    lines: list[str] = []
    for sec in doc.sections[:1]:  # dados de contato às vezes ficam no cabeçalho
        lines += [p.text.strip() for p in sec.header.paragraphs if p.text.strip()]
    first = not lines
    for p in doc.paragraphs:
        md = _para_md(p, first)
        if md:
            lines.append(md)
            first = False
    for t in doc.tables:  # muitos CVs usam tabela para layout
        for row in t.rows:
            cells: list[str] = []
            for c in row.cells:
                if c.text.strip() and c.text.strip() not in cells:
                    cells.append(c.text.strip())
            if cells:
                lines.append(" | ".join(cells))
    out = ""
    for i, ln in enumerate(lines):  # itens de lista seguidos ficam colados
        sep = "\n" if i and ln.startswith("- ") and lines[i - 1].startswith("- ") else "\n\n"
        out += (sep if i else "") + ln
    return out


def _plain_to_md(text: str) -> str:
    """Texto de PDF em markdown, sem mudar palavras: junta linhas quebradas, marca listas e títulos."""
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if out and out[-1] != "":
                out.append("")
            continue
        if BULLET_RE.match(line):
            out.append(f"- {BULLET_RE.sub('', line)}")
            continue
        letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", line)
        if len(letters) >= 3 and line.isupper() and len(line) < 50:
            out += ["", f"## {line}", ""]
            continue
        prev = out[-1] if out else ""
        # linha quebrada no meio da frase: continua a anterior
        if prev and not prev.startswith("#") and not re.search(r"[.:;!?|]$", prev) and re.match(r"^[a-zà-ÿ(0-9,]", line):
            out[-1] = f"{prev} {line}"
        else:
            out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _convert_to_docx(data: bytes, ext: str) -> bytes:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise ImportError_(f"Arquivo {ext} precisa do LibreOffice para converter. Salve como DOCX ou PDF e envie de novo.")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"cv{ext}"
        src.write_bytes(data)
        subprocess.run([soffice, "--headless", "--convert-to", "docx", "--outdir", tmp, str(src)],
                       capture_output=True, timeout=120)
        out = Path(tmp) / "cv.docx"
        if not out.exists():
            raise ImportError_(f"Não consegui converter o arquivo {ext}. Salve como DOCX ou PDF e envie de novo.")
        return out.read_bytes()


def extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        raise ImportError_("Formato não aceito. Envie PDF, DOCX ou DOC.")
    if len(data) > MAX_BYTES:
        raise ImportError_("Arquivo maior que 10 MB.")
    if ext == ".pdf":
        text = _plain_to_md(_pdf_text(data))
    elif ext == ".docx":
        text = _docx_text(data)
    elif ext == ".md":
        text = data.decode("utf-8", errors="replace")
    elif ext == ".txt":
        text = _plain_to_md(data.decode("utf-8", errors="replace"))
    else:
        text = _docx_text(_convert_to_docx(data, ext))
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(re.sub(r"\s", "", text)) < 200:
        raise ImportError_(
            "Quase nenhum texto saiu do arquivo. Provavelmente é um PDF escaneado (imagem), "
            "que os sistemas de triagem também não conseguem ler. Exporte o PDF a partir do Word/Google Docs ou envie o DOCX."
        )
    return text


def _uploads(profile_id: int) -> Path:
    return get_settings().data_dir / "uploads" / str(profile_id)


def save_original(profile_id: int, filename: str, data: bytes) -> str:
    d = _uploads(profile_id)
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("cv_original.*"):
        old.unlink()
    ext = Path(filename).suffix.lower()
    (d / f"cv_original{ext}").write_bytes(data)
    (d / "cv_original.json").write_text(json.dumps({"nome": filename}), encoding="utf-8")
    return filename


def original_file(profile_id: int) -> tuple[Path, str] | None:
    d = _uploads(profile_id)
    meta = d / "cv_original.json"
    if not meta.exists():
        return None
    nome = json.loads(meta.read_text(encoding="utf-8"))["nome"]
    f = next((p for p in d.glob("cv_original.*") if p.suffix != ".json"), None)
    return (f, nome) if f else None


# ------------------------------------------------------------------ IA

class CVImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: str
    fatos_yaml: str = Field(description="Banco de fatos completo em YAML, no schema da Fase 0")
    cv_base_md: str = Field(description="CV base em markdown, coluna única, estrutura da Fase 3")
    correcoes: list[str] = Field(description="As 5 correções de maior impacto, em ordem (Fase 1)")
    pontos_fortes: list[str] = Field(description="O que já está forte e não pode se perder")
    perguntas: list[str] = Field(description="Perguntas para destravar números e confirmar fatos pendentes (Fase 2)")


class CVFatos(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: str
    fatos_yaml: str = Field(description="Banco de fatos completo em YAML, no schema da Fase 0")
    correcoes: list[str] = Field(description="As 5 correções de maior impacto, em ordem (Fase 1)")
    pontos_fortes: list[str] = Field(description="O que já está forte e não pode se perder")
    perguntas: list[str] = Field(description="Perguntas para destravar números e confirmar fatos pendentes (Fase 2)")


def facts_system() -> str:
    return (
        "Você faz o onboarding do currículo no app AI-JOB-FINDER, seguindo a skill abaixo. A pessoa escolheu manter "
        "o texto do CV como está: você NÃO reescreve o CV.\n\n"
        "Execute:\n"
        "1. Fase 0: extraia TODOS os fatos do texto para 'fatos_yaml', no schema da skill, com IDs (EXP1, EXP1.F1, "
        "PRJ1, CER1...). Copie o conteúdo original. Tudo que precisa de número ou confirmação fica com "
        "status: pendente. O YAML precisa ser válido (aspas em strings com ':' ou '#').\n"
        "2. Fase 1 resumida: as 5 correções de maior impacto e os pontos fortes, só como sugestão; a pessoa decide.\n"
        "3. 'perguntas': as perguntas da Fase 2 que mais destravam números, no máximo 12.\n\n"
        "Nunca invente número, ferramenta, cargo, data ou resultado.\n\n"
        "=== SKILL cv-diagnostico-e-perfil ===\n" + skill_text("cv-diagnostico-e-perfil")
    )


def import_system() -> str:
    return (
        "Você faz o onboarding do currículo no app AI-JOB-FINDER, seguindo a skill abaixo. Nesta etapa NÃO há "
        "entrevista: a pessoa acabou de enviar o arquivo.\n\n"
        "Execute:\n"
        "1. Fase 0: extraia TODOS os fatos do texto para 'fatos_yaml', no schema da skill, com IDs (EXP1, EXP1.F1, "
        "PRJ1, CER1...). Copie o conteúdo original; não melhore nada aqui. Tudo que precisa de número ou confirmação "
        "fica com status: pendente. O YAML precisa ser válido (aspas em strings com ':' ou '#').\n"
        "2. Fase 1 resumida: as 5 correções de maior impacto e os pontos fortes.\n"
        "3. Fase 3: escreva o 'cv_base_md' para o cargo-alvo principal (use a área de prioridade 1 dos filtros, se "
        "houver). Onde faltar número, use o marcador [[...]] descrevendo o que perguntar, como na skill. Todo bullet "
        "precisa sair de um fato do fatos_yaml.\n"
        "4. 'perguntas': as perguntas da Fase 2 que mais destravam números, agrupadas por experiência, no máximo 12.\n\n"
        "Formato do cv_base_md: '# Nome', linha de contatos, título-alvo em negrito, '## Resumo', "
        "'## Experiência Profissional', '### Cargo | Empresa | mmm/aaaa - mmm/aaaa', bullets com '- ', "
        "depois '## Formação', '## Projetos e Pesquisa', '## Habilidades', '## Certificações', '## Idiomas'. "
        "Sem tabelas, ícones ou imagens.\n\n"
        "Nunca invente número, ferramenta, cargo, data ou resultado.\n\n"
        "=== SKILL cv-diagnostico-e-perfil ===\n" + skill_text("cv-diagnostico-e-perfil")
    )


def import_user(texto: str, filtros_yaml: str, feedback: str = "") -> str:
    parts = [f"<texto_do_curriculo>\n{texto}\n</texto_do_curriculo>"]
    if filtros_yaml.strip():
        parts.append(f"<filtros_atuais>\n{filtros_yaml}\n</filtros_atuais>")
    if feedback:
        parts.append(f"<correcao>\nA resposta anterior teve este problema; corrija:\n{feedback}\n</correcao>")
    return "\n\n".join(parts)


def run_import(texto: str, filtros_yaml: str, modo: str = "otimizar") -> tuple[CVImport, str]:
    """modo 'otimizar': IA escreve fatos + CV base. modo 'como_esta': o texto do CV vira o CV base; IA só faz fatos."""
    from .ai.providers import get_provider

    provider = get_provider()
    s = get_settings()
    if modo == "como_esta":
        if provider.name == "mock":
            return CVImport(nome="", fatos_yaml="", cv_base_md=texto, correcoes=[], pontos_fortes=[], perguntas=[]), "mock"
        f = provider.structured(facts_system(), import_user(texto, ""), CVFatos, s.ai_model_cv, "medium")
        try:
            yaml.safe_load(f.fatos_yaml)
        except yaml.YAMLError as e:
            f = provider.structured(facts_system(), import_user(texto, "", f"fatos_yaml inválido: {e}"),
                                    CVFatos, s.ai_model_cv, "medium")
            yaml.safe_load(f.fatos_yaml)
        return CVImport(cv_base_md=texto, **f.model_dump()), f"{provider.name}:{s.ai_model_cv}"
    if provider.name == "mock":
        return CVImport(nome="", fatos_yaml="", cv_base_md=texto, correcoes=["(mock) sem IA: o texto extraído virou o CV base"],
                        pontos_fortes=[], perguntas=[]), "mock"
    out = provider.structured(import_system(), import_user(texto, filtros_yaml), CVImport, s.ai_model_cv, "medium")
    try:
        yaml.safe_load(out.fatos_yaml)
    except yaml.YAMLError as e:
        out = provider.structured(import_system(), import_user(texto, filtros_yaml, f"fatos_yaml inválido: {e}"),
                                  CVImport, s.ai_model_cv, "medium")
        yaml.safe_load(out.fatos_yaml)
    return out, f"{provider.name}:{s.ai_model_cv}"
