from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc)


COLUMNS = ["selecionadas", "candidatura", "entrevista", "desafio", "aprovado", "descartadas"]


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    criado_em: datetime = Field(default_factory=now)


class Profile(SQLModel, table=True):
    __tablename__ = "profiles"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, index=True)  # dono do perfil (um perfil por usuário)
    nome: str
    fatos_yaml: str = ""
    cv_base_md: str = ""
    filtros_yaml: str = ""
    regras_cv: str = ""  # regras de escrita da pessoa candidata para o CV adaptado (texto livre)
    atualizado_em: datetime = Field(default_factory=now)


class Schedule(SQLModel, table=True):
    __tablename__ = "schedules"
    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profiles.id", index=True)
    intervalo_horas: float = 6.0
    ativo: bool = True
    ultima_execucao: datetime | None = None
    cursor: int = 0  # próxima busca (rodízio entre títulos x locais)


class Run(SQLModel, table=True):
    __tablename__ = "runs"
    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profiles.id", index=True)
    origem: str = "agenda"  # agenda | manual | mcp
    status: str = "rodando"  # rodando | ok | erro
    iniciado_em: datetime = Field(default_factory=now)
    terminado_em: datetime | None = None
    buscas: int = 0
    encontradas: int = 0
    novas: int = 0
    analisadas: int = 0
    log: str = ""


class Job(SQLModel, table=True):
    __tablename__ = "jobs"
    id: int | None = Field(default=None, primary_key=True)
    hash: str = Field(index=True, unique=True)
    fonte: str = ""
    url: str = Field(default="", index=True)
    cargo: str = ""
    empresa: str = ""
    local: str = ""
    remoto: bool | None = None
    modelo: str = ""  # remoto | hibrido | presencial | ""
    tipo: str = ""
    salario_min: float | None = None
    salario_max: float | None = None
    salario_intervalo: str = ""
    moeda: str = ""
    publicada_em: datetime | None = None
    descricao: str = ""
    termo_busca: str = ""
    raw_json: str = ""
    visto_em: datetime = Field(default_factory=now)


class ProfileJob(SQLModel, table=True):
    """Quais vagas foram encontradas para qual perfil. A vaga é global (deduplicada), mas cada
    perfil só analisa e vê as vagas que as buscas dele trouxeram."""

    __tablename__ = "profile_jobs"
    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profiles.id", index=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    criado_em: datetime = Field(default_factory=now)


class Analysis(SQLModel, table=True):
    __tablename__ = "analyses"
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    profile_id: int = Field(foreign_key="profiles.id", index=True)
    cache_key: str = Field(default="", index=True)
    veredito: str = ""  # APROVADA | ALERTA | DESCARTADA
    filtro_motivos_json: str = "[]"
    score: int | None = None
    tag: str = ""  # quente | morna | fria | ""
    resumo: str = ""
    motivos_json: str = "[]"
    requisitos_json: str = "[]"
    lacunas_json: str = "[]"
    alertas_json: str = "[]"
    modelo: str = ""
    criado_em: datetime = Field(default_factory=now)


class Card(SQLModel, table=True):
    __tablename__ = "cards"
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    profile_id: int = Field(foreign_key="profiles.id", index=True)
    coluna: str = "selecionadas"
    posicao: float = 0
    notas: str = ""
    prazo: str = ""
    movido_em: datetime = Field(default_factory=now)
    criado_em: datetime = Field(default_factory=now)


class CardEvent(SQLModel, table=True):
    __tablename__ = "card_events"
    id: int | None = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="cards.id", index=True)
    de: str = ""
    para: str = ""
    autor: str = ""
    criado_em: datetime = Field(default_factory=now)


class GeneratedCV(SQLModel, table=True):
    __tablename__ = "generated_cvs"
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    profile_id: int = Field(foreign_key="profiles.id", index=True)
    cv_md: str = ""
    relatorio_md: str = ""
    diff_md: str = ""
    veracidade_json: str = "[]"
    mensagem_recrutador: str = ""
    validacao_json: str = "[]"  # problemas encontrados pelo validador
    arquivo_base: str = ""  # nome do arquivo sem extensão
    nota: str = ""  # "gerado" ou o pedido de ajuste que criou esta versão
    modelo: str = ""
    criado_em: datetime = Field(default_factory=now)
