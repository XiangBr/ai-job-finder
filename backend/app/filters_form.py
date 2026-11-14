"""Formulário de filtros: conversão filtros.yaml <-> JSON do formulário e preenchimento por IA."""

import copy
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class _S(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Cargo(_S):
    area: str
    prioridade: int
    titulos: list[str] = Field(description="Títulos de busca, PT e EN, formas masculina e feminina")


class Remoto(_S):
    aceita: bool
    prioridade: int
    abrangencia: str = Field(description="Ex.: Brasil, América Latina, Mundo")


class Presencial(_S):
    aceita: bool
    prioridade: int
    cidades: list[str] = Field(description="Formato 'Cidade - UF'")


class ModeloTrabalho(_S):
    remoto: Remoto
    hibrido: Presencial
    presencial: Presencial


class Remuneracao(_S):
    estagio_minimo_bolsa: int | None = Field(description="R$ por mês")
    clt_minimo_base: int | None = Field(description="R$ por mês")
    clt_exige: list[str] = Field(description="Benefícios obrigatórios, ex.: VR, VT, plano de saúde")
    pj_minimo: int | None = Field(description="R$ por mês")
    nao_informado: Literal["marcar", "descartar"] = Field(description="O que fazer com vaga sem salário")


class Restricoes(_S):
    disponibilidade_estagio_max_meses: int | None = Field(description="Meses até a formatura")
    anos_experiencia_max: int | None
    exige_formado: bool


class FiltrosForm(_S):
    cargos: list[Cargo]
    excluir_titulos: list[str] = Field(description="Palavras que eliminam a vaga se aparecem no título")
    nivel: list[str] = Field(description="estagio, trainee, junior, analista, pleno, senior...")
    contrato: list[str] = Field(description="estagio, clt, pj...")
    modelo_trabalho: ModeloTrabalho
    raio_km: int | None
    aceita_mudanca: bool
    remuneracao: Remuneracao
    empresas_alvo: list[str]
    empresas_bloqueadas: list[str]
    setores_preferidos: list[str]
    setores_evitar: list[str]
    idiomas_vaga: list[str] = Field(description="Códigos: pt, en, es")
    ingles_maximo_exigido: str = Field(description="básico, intermediário, avançado ou fluente")
    restricoes: Restricoes
    palavras_excluir: list[str] = Field(description="Palavras que eliminam a vaga se aparecem no título ou descrição")
    publicada_ha_no_maximo_dias: int
    fontes: list[str] = Field(description="linkedin, indeed, glassdoor, google")
    score_minimo_para_alerta: int
    filtrar_titulo_fora_da_area: bool = Field(description="Descartar antes da IA vagas cujo título não tem palavra das áreas")
    observacoes: str = Field(description="Preferências em texto livre que não cabem nos outros campos")


class FiltrosIA(_S):
    filtros: FiltrosForm
    resumo: str = Field(description="1 a 3 frases curtas dizendo o que mudou")
    perguntas: list[str] = Field(description="Até 2 perguntas sobre pontos ambíguos; vazio se não houver")


# ------------------------------------------------------------------ conversão

def _clean(v):
    """'A_CONFIRMAR', None e '' viram vazio."""
    if isinstance(v, str) and v.strip().upper() in ("A_CONFIRMAR", ""):
        return None
    return v


def _list(v) -> list[str]:
    v = _clean(v)
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if _clean(x) is not None]
    return [s.strip() for s in str(v).split(",") if s.strip()]


def _int(v) -> int | None:
    v = _clean(v)
    try:
        return int(float(v)) if v is not None else None
    except (TypeError, ValueError):
        return None


def _bool(v, default=False) -> bool:
    v = _clean(v)
    return bool(v) if isinstance(v, bool) else default


def parse_root(text: str) -> tuple[dict, dict]:
    """Retorna (raiz do yaml, dicionário perfil_busca)."""
    try:
        root = yaml.safe_load(text or "") or {}
    except yaml.YAMLError:
        root = {}
    if not isinstance(root, dict):
        root = {}
    pb = root.get("perfil_busca", root)
    return root, pb if isinstance(pb, dict) else {}


def yaml_to_form(text: str) -> FiltrosForm:
    _, f = parse_root(text)
    mt = f.get("modelo_trabalho") or {}
    rem = f.get("remuneracao") or {}
    res = f.get("restricoes_eliminatorias") or {}

    def loc(k, prio):
        c = mt.get(k) or {}
        return Presencial(aceita=_bool(c.get("aceita")), prioridade=_int(c.get("prioridade")) or prio,
                          cidades=_list(c.get("cidades")))

    r = mt.get("remoto") or {}
    return FiltrosForm(
        cargos=[
            Cargo(area=str(c.get("area", "")), prioridade=_int(c.get("prioridade")) or i + 1, titulos=_list(c.get("titulos")))
            for i, c in enumerate(f.get("cargos") or []) if isinstance(c, dict)
        ],
        excluir_titulos=_list(f.get("excluir_titulos")),
        nivel=_list(f.get("nivel")),
        contrato=_list(f.get("contrato")),
        modelo_trabalho=ModeloTrabalho(
            remoto=Remoto(aceita=_bool(r.get("aceita"), True), prioridade=_int(r.get("prioridade")) or 1,
                          abrangencia=str(_clean(r.get("abrangencia")) or "Brasil")),
            hibrido=loc("hibrido", 2),
            presencial=loc("presencial", 3),
        ),
        raio_km=_int(f.get("raio_km")),
        aceita_mudanca=_bool(f.get("aceita_mudanca")),
        remuneracao=Remuneracao(
            estagio_minimo_bolsa=_int((rem.get("estagio") or {}).get("minimo_bolsa")),
            clt_minimo_base=_int((rem.get("clt") or {}).get("minimo_base")),
            clt_exige=_list((rem.get("clt") or {}).get("exige")),
            pj_minimo=_int((rem.get("pj") or {}).get("minimo")),
            nao_informado="descartar" if rem.get("nao_informado") == "descartar" else "marcar",
        ),
        empresas_alvo=_list(f.get("empresas_alvo")),
        empresas_bloqueadas=_list(f.get("empresas_bloqueadas")),
        setores_preferidos=_list(f.get("setores_preferidos")),
        setores_evitar=_list(f.get("setores_evitar")),
        idiomas_vaga=_list(f.get("idiomas_vaga")) or ["pt"],
        ingles_maximo_exigido=str(_clean(f.get("ingles_maximo_exigido")) or ""),
        restricoes=Restricoes(
            disponibilidade_estagio_max_meses=_int(res.get("disponibilidade_estagio_max_meses")),
            anos_experiencia_max=_int(res.get("anos_experiencia_max")),
            exige_formado=_bool(res.get("exige_formado")),
        ),
        palavras_excluir=_list(f.get("palavras_excluir")),
        publicada_ha_no_maximo_dias=_int(f.get("publicada_ha_no_maximo_dias")) or 7,
        fontes=_list(f.get("fontes")) or ["linkedin", "indeed"],
        score_minimo_para_alerta=_int(f.get("score_minimo_para_alerta")) or 65,
        filtrar_titulo_fora_da_area=f.get("filtrar_titulo_fora_da_area") is not False,
        observacoes=str(_clean(f.get("observacoes")) or ""),
    )


def form_to_yaml(form: FiltrosForm, old_text: str) -> str:
    """Grava o formulário por cima do yaml antigo, preservando chaves que o formulário não conhece."""
    root, old = parse_root(old_text)
    pb = copy.deepcopy(old)
    m = form.modelo_trabalho
    rem = form.remuneracao
    pb.update({
        "cargos": [c.model_dump() for c in sorted(form.cargos, key=lambda c: c.prioridade)],
        "excluir_titulos": form.excluir_titulos,
        "nivel": form.nivel,
        "contrato": form.contrato,
        "modelo_trabalho": {
            "remoto": m.remoto.model_dump(),
            "hibrido": m.hibrido.model_dump(),
            "presencial": m.presencial.model_dump(),
        },
        "raio_km": form.raio_km,
        "aceita_mudanca": form.aceita_mudanca,
        "remuneracao": {
            "estagio": {"minimo_bolsa": rem.estagio_minimo_bolsa},
            "clt": {"minimo_base": rem.clt_minimo_base, "exige": rem.clt_exige},
            "pj": {"minimo": rem.pj_minimo},
            "nao_informado": rem.nao_informado,
        },
        "empresas_alvo": form.empresas_alvo,
        "empresas_bloqueadas": form.empresas_bloqueadas,
        "setores_preferidos": form.setores_preferidos,
        "setores_evitar": form.setores_evitar,
        "idiomas_vaga": form.idiomas_vaga,
        "ingles_maximo_exigido": form.ingles_maximo_exigido or None,
        "restricoes_eliminatorias": {
            **(old.get("restricoes_eliminatorias") or {}),
            **form.restricoes.model_dump(),
        },
        "palavras_excluir": form.palavras_excluir,
        "publicada_ha_no_maximo_dias": form.publicada_ha_no_maximo_dias,
        "fontes": form.fontes,
        "score_minimo_para_alerta": form.score_minimo_para_alerta,
        "filtrar_titulo_fora_da_area": form.filtrar_titulo_fora_da_area,
        "observacoes": form.observacoes,
    })
    if "perfil_busca" in root:
        out = {**{k: v for k, v in root.items() if k != "perfil_busca"}, "perfil_busca": pb}
    else:
        out = {"perfil_busca": pb}
    header = "# Filtros de vaga. Editado pela tela de filtros do AI-JOB-FINDER.\n"
    return header + yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=120)


# ------------------------------------------------------------------ IA

FILL_SYSTEM = """Você preenche o formulário de preferências de busca de vagas do app AI-JOB-FINDER a partir do que a pessoa escreve em texto livre.

Você recebe o formulário atual (JSON) e a mensagem nova (e, às vezes, as mensagens anteriores da conversa).
Devolva o formulário COMPLETO atualizado:
- Mude só o que a mensagem pede ou implica com clareza. Todo o resto fica exatamente igual.
- "Também", "além disso", "adiciona" somam aos valores atuais. "Só", "apenas", "troca por", "tira" substituem ou removem.
- Cargos: cada área tem uma prioridade (1 = mais importante) e uma lista de títulos de busca. Gere títulos que um recrutador brasileiro usaria, em português e inglês, nas formas masculina e feminina quando houver flexão (ex.: "Analista de Dados", "Data Analyst", "Estágio em Dados"). No máximo 8 títulos por área.
- Cidades no formato "Cidade - UF". Valores de salário em reais por mês, inteiros.
- Nível e contrato usam palavras minúsculas sem acento: estagio, trainee, junior, analista, pleno, senior; estagio, clt, pj.
- Fontes possíveis: linkedin, indeed, glassdoor, google.
- Se a pessoa descrever algo que não cabe em nenhum campo (cultura, tipo de time, horário, propósito), resuma em "observacoes" sem apagar o que já estava lá.
- Não invente preferências que a pessoa não disse.
- "resumo": 1 a 3 frases curtas, em português, dizendo o que mudou.
- "perguntas": até 2 perguntas sobre algo ambíguo que valha confirmar; vazio se estiver claro."""


def fill_user(texto: str, form: FiltrosForm, historico: list[dict]) -> str:
    hist = "\n".join(f"{m.get('role', 'user')}: {m.get('text', '')}" for m in historico[-6:])
    return (
        f"<formulario_atual>\n{form.model_dump_json(indent=1)}\n</formulario_atual>\n\n"
        + (f"<conversa_anterior>\n{hist}\n</conversa_anterior>\n\n" if hist else "")
        + f"<mensagem>\n{texto}\n</mensagem>"
    )
