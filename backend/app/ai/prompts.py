import json
import re
from functools import lru_cache

from ..config import get_settings


@lru_cache
def skill_text(name: str) -> str:
    path = get_settings().skills_dir / name / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    return re.sub(r"^---.*?---\s*", "", text, count=1, flags=re.S)  # tira o frontmatter


def analyze_system() -> str:
    return (
        "Você é o motor de triagem de vagas do app AI-JOB-FINDER. Siga a skill abaixo, "
        "executando APENAS os passos 1 a 3 (filtros, leitura da vaga, aderência e score). "
        "Não reescreva o CV. Responda somente no formato JSON pedido. Escreva em português.\n\n"
        "Regras do JSON:\n"
        "- score segue a fórmula da skill (60% obrigatórios, 25% responsabilidades, 15% desejáveis).\n"
        "- veredito DESCARTADA só quando a descrição mostrar um bloqueio eliminatório que o filtro em código não pegou "
        "(ex.: presencial fora das cidades aceitas, nível sênior). Bloqueios que o candidato pode querer revisar "
        "(disponibilidade de estágio maior que o prazo até a formatura, inglês acima do nível) viram ALERTA, "
        "com o motivo em 'alertas'.\n"
        "- 'alertas' é SÓ para bloqueios que a pessoa candidata precisa decidir (disponibilidade, inglês, anos de experiência, "
        "formação exigida, localização duvidosa). Não coloque ali salário não informado, comentário sobre o score, "
        "fatos pendentes nem dicas: isso vai em 'lacunas' ou fica de fora. Sem bloqueio, 'alertas' fica vazio "
        "e o veredito é APROVADA.\n"
        "- Cada requisito aponta os IDs de fatos.yaml que servem de evidência. Nunca invente fato.\n"
        "- motivos: exatamente os 3 principais motivos de fit, curtos.\n\n"
        "=== SKILL cv-adaptar-vaga ===\n" + skill_text("cv-adaptar-vaga")
    )


def tailor_system() -> str:
    return (
        "Você é o gerador de CVs adaptados do app AI-JOB-FINDER. Siga a skill abaixo do passo 2 ao 6 "
        "(a vaga já passou nos filtros). Responda somente no formato JSON pedido.\n\n"
        "Regras invioláveis (o backend valida e rejeita):\n"
        "- Todo bullet do cv_md precisa aparecer em 'veracidade' com o texto exato e os IDs de fatos.yaml que o sustentam.\n"
        "- Nenhum número, ferramenta, certificação ou resultado que não esteja em fatos.yaml. Onde faltar número, "
        "use o marcador [[...]] descrevendo o que falta, como no CV base.\n"
        "- O cv_md é markdown simples, coluna única: '# Nome', linha de contatos, '## Seção', '### Cargo | Empresa | período', "
        "bullets com '- '. Sem tabelas, sem ícones, sem imagens.\n"
        "- Se a vaga estiver em inglês, gere o CV em inglês (idioma 'en') com os mesmos fatos.\n\n"
        "=== SKILL cv-adaptar-vaga ===\n" + skill_text("cv-adaptar-vaga")
    )


def job_block(job) -> str:
    sal = "a confirmar"
    if job.salario_min or job.salario_max:
        sal = f"{job.moeda or ''} {job.salario_min or ''}–{job.salario_max or ''} ({job.salario_intervalo or 's/ intervalo'})"
    return (
        f"Cargo: {job.cargo}\nEmpresa: {job.empresa}\nLocal: {job.local or 'não informado'}\n"
        f"Modelo: {job.modelo or 'não informado'}\nSalário: {sal}\nFonte: {job.fonte}\nURL: {job.url}\n"
        f"Publicada em: {job.publicada_em.date() if job.publicada_em else 'não informado'}\n\n"
        f"Descrição:\n{job.descricao or '(sem descrição)'}"
    )


def analyze_user(job, fatos_yaml: str, filtros_yaml: str, filtro_codigo: dict) -> str:
    return (
        "<vaga>\n" + job_block(job) + "\n</vaga>\n\n"
        "<fatos_yaml>\n" + fatos_yaml + "\n</fatos_yaml>\n\n"
        "<filtros_yaml>\n" + filtros_yaml + "\n</filtros_yaml>\n\n"
        "<resultado_filtro_em_codigo>\n" + json.dumps(filtro_codigo, ensure_ascii=False) + "\n</resultado_filtro_em_codigo>"
    )


REGRAS_NOTA = (
    "Estas são as regras de escrita da própria pessoa candidata. Elas têm prioridade sobre as técnicas de escrita da skill "
    "(fórmula XYZ, espelhamento de vocabulário, estrutura do resumo, ordem das seções, tamanho). Elas NÃO têm "
    "prioridade sobre: nada inventado, veracidade (cada bullet com IDs de fatos) e o formato markdown de coluna única."
)


def regras_block(regras: str) -> str:
    regras = (regras or "").strip()
    if not regras:
        return ""
    return f"<regras_da_pessoa_candidata>\n{regras}\n</regras_da_pessoa_candidata>\n{REGRAS_NOTA}"


def tailor_user(job, fatos_yaml: str, cv_base_md: str, analise: dict | None, feedback: str = "", regras: str = "") -> str:
    parts = [
        "<vaga>\n" + job_block(job) + "\n</vaga>",
        "<fatos_yaml>\n" + fatos_yaml + "\n</fatos_yaml>",
        "<cv_base_md>\n" + cv_base_md + "\n</cv_base_md>",
    ]
    if regras_block(regras):
        parts.append(regras_block(regras))
    if analise:
        parts.append("<pre_analise>\n" + json.dumps(analise, ensure_ascii=False) + "\n</pre_analise>")
    if feedback:
        parts.append(
            "<correcao>\nA versão anterior foi rejeitada pelo validador de veracidade por estes motivos. "
            "Corrija sem inventar nada:\n" + feedback + "\n</correcao>"
        )
    return "\n\n".join(parts)
