from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Requisito(_Strict):
    requisito: str
    tipo: Literal["obrigatorio", "desejavel", "responsabilidade"]
    classificacao: Literal["forte", "parcial", "lacuna", "bloqueio"]
    evidencia: str = Field(description="Fato do candidato que cobre o requisito, ou vazio")
    fatos_ids: list[str] = Field(description="IDs de fatos.yaml usados como evidência")


class Analise(_Strict):
    veredito: Literal["APROVADA", "ALERTA", "DESCARTADA"]
    score: int = Field(description="0 a 100, pela fórmula 60/25/15 da skill")
    problema_empregador: str = Field(description="Uma frase: o que essa pessoa vai resolver")
    motivos: list[str] = Field(description="Os 3 principais motivos de fit")
    requisitos: list[Requisito]
    lacunas: list[str]
    alertas: list[str] = Field(description="Bloqueios revisáveis e avisos (disponibilidade, inglês...)")
    motivo_descarte: str = Field(description="Se DESCARTADA, motivo em uma linha; senão vazio")


class Veracidade(_Strict):
    bullet: str = Field(description="Texto exato do bullet como está no cv_md")
    fatos_ids: list[str]


class Lacuna(_Strict):
    lacuna: str
    como_tratar: str


class PerguntaEntrevista(_Strict):
    pergunta: str
    roteiro_star: str


class CVAdaptado(_Strict):
    idioma: Literal["pt", "en"]
    titulo_alvo: str
    fio_narrativo: str
    cv_md: str = Field(description="CV completo em markdown, coluna única")
    veracidade: list[Veracidade] = Field(description="Uma linha por bullet do cv_md")
    diff: list[str] = Field(description="O que mudou contra o CV base")
    lacunas: list[Lacuna]
    mensagem_recrutador: str = Field(description="Até 300 caracteres, com um fato concreto")
    perguntas_entrevista: list[PerguntaEntrevista]
    cobertura_palavras_chave: str = Field(description="Ex.: '7 de 10 obrigatórios (70%)'")
