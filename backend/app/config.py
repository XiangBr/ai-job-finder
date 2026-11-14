from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", ".env"), extra="ignore")

    data_dir: Path = ROOT / "data"
    skills_dir: Path = ROOT / "skills"
    frontend_dist: Path = ROOT / "frontend" / "dist"

    # Sessão e login
    secret_key: str = "troque-isto"
    session_days: int = 30
    cookie_secure: bool = False
    # Usuários criados no primeiro boot: "ana:senha1,bruno:senha2"
    bootstrap_users: str = ""

    # MCP (Hermes / Claude). Vazio = MCP desligado.
    mcp_token: str = ""
    # Usuário cujo perfil o MCP enxerga (vazio = primeiro usuário)
    mcp_user: str = ""

    # Perfil inicial (pasta com fatos.yaml, filtros.yaml e um *_CV_base.md), vai para o primeiro usuário
    seed_profile_dir: Path | None = None
    seed_profile_name: str = "Perfil"
    # Bancos antigos (perfil único): dono do perfil existente (vazio = primeiro usuário)
    legacy_profile_owner: str = ""

    # IA. Valores de AI_PROVIDER (ver backend/app/ai/providers.py e docs/provedores-de-ia.md):
    #   claude_cli  Claude Code instalado (assinatura ou chave)    anthropic  API da Anthropic
    #   codex_cli   Codex CLI instalado (assinatura ou chave)       openai     API da OpenAI
    #   openrouter  OpenRouter (qualquer modelo)                    gemini     API do Google Gemini
    #   ollama      modelo local no Ollama                          compatible qualquer API compatível com OpenAI
    #   mock        sem IA (heurística), para testar o fluxo
    ai_provider: str = "mock"
    # Vazio = padrão do provedor (ver DEFAULT_MODELS em providers.py)
    ai_model_triage: str = ""
    ai_model_cv: str = ""
    ai_timeout: int = 600

    claude_cli_bin: str = "claude"
    claude_cli_timeout: int = 600
    codex_cli_bin: str = "codex"

    # APIs compatíveis com OpenAI (openai, openrouter, gemini, ollama, compatible)
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    gemini_api_key: str = ""
    # Sobrescreve a URL base do provedor (obrigatória em AI_PROVIDER=compatible)
    ai_base_url: str = ""
    ai_api_key: str = ""

    # Coleta
    jobspy_proxies: str = ""  # "user:pass@host:port,host2:port"
    max_searches_per_run: int = 12
    results_per_search: int = 15
    min_seconds_between_searches: float = 4.0
    min_minutes_between_runs: int = 30
    analyze_max_per_run: int = 150

    @property
    def db_url(self) -> str:
        return f"sqlite:///{(self.data_dir / 'app.db').as_posix()}"

    @property
    def cv_dir(self) -> Path:
        return self.data_dir / "cvs"


# Modelo padrão (triagem, CV) por provedor, usado quando AI_MODEL_TRIAGE / AI_MODEL_CV estão vazios.
# Modelos mudam rápido: confira o nome atual no site do provedor e defina no .env se preciso.
# "" = deixa a ferramenta escolher (Codex usa o modelo do seu ~/.codex/config.toml).
DEFAULT_MODELS: dict[str, tuple[str, str]] = {
    "claude_cli": ("claude-sonnet-5-5", "claude-opus-5-5"),
    "anthropic": ("claude-sonnet-5-5", "claude-opus-5-5"),
    "codex_cli": ("", ""),
    "openai": ("gpt-5-mini", "gpt-5"),
    "openrouter": ("openai/gpt-5-mini", "anthropic/claude-sonnet-5.5"),
    "gemini": ("gemini-2.5-flash", "gemini-2.5-pro"),
    "ollama": ("qwen3:8b", "qwen3:14b"),
    "compatible": ("", ""),
    "mock": ("mock", "mock"),
}


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ai_provider = s.ai_provider.strip().lower() or "mock"
    triage, cv = DEFAULT_MODELS.get(s.ai_provider, ("", ""))
    s.ai_model_triage = s.ai_model_triage.strip() or triage
    s.ai_model_cv = s.ai_model_cv.strip() or cv
    s.data_dir.mkdir(parents=True, exist_ok=True)
    s.cv_dir.mkdir(parents=True, exist_ok=True)
    return s
