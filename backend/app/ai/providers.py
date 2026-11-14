"""Provedores de IA plugáveis, escolhidos por AI_PROVIDER.

Todos implementam um único método, `structured(system, user, schema, model, effort)`, que devolve
um objeto Pydantic. O resto do app (análise de vaga, CV adaptado, chat) só chama esse método.

- claude_cli   Claude Code headless (`claude -p`), assinatura ou chave
- anthropic    SDK da Anthropic, structured outputs
- codex_cli    Codex CLI (`codex exec --output-schema`), assinatura ChatGPT ou chave
- openai / openrouter / gemini / ollama / compatible   Chat Completions no formato OpenAI
- mock         heurística sem IA, para testar o fluxo

Para adicionar outro provedor: crie uma classe com `name` e `structured()` e registre em get_provider().
"""

import json
import logging
import os
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

from ..config import get_settings
from . import prompts
from .schemas import Analise, CVAdaptado, Requisito, Veracidade

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class AIError(RuntimeError):
    pass


class Provider:
    name = "base"

    def structured(self, system: str, user: str, schema: type[T], model: str, effort: str) -> T:
        raise NotImplementedError

    def analyze_job(self, job, fatos_yaml, filtros_yaml, filtro_codigo) -> tuple[Analise, str]:
        s = get_settings()
        out = self.structured(
            prompts.analyze_system(),
            prompts.analyze_user(job, fatos_yaml, filtros_yaml, filtro_codigo),
            Analise,
            s.ai_model_triage,
            "low",
        )
        return out, f"{self.name}:{s.ai_model_triage}"

    def tailor_cv(self, job, fatos_yaml, cv_base_md, analise, feedback="", regras="") -> tuple[CVAdaptado, str]:
        s = get_settings()
        out = self.structured(
            prompts.tailor_system(),
            prompts.tailor_user(job, fatos_yaml, cv_base_md, analise, feedback, regras),
            CVAdaptado,
            s.ai_model_cv,
            "high",
        )
        return out, f"{self.name}:{s.ai_model_cv}"


    def fill_filters(self, texto, form, historico):
        from ..filters_form import FILL_SYSTEM, FiltrosIA, fill_user

        s = get_settings()
        out = self.structured(FILL_SYSTEM, fill_user(texto, form, historico), FiltrosIA, s.ai_model_triage, "low")
        return out, f"{self.name}:{s.ai_model_triage}"


class ClaudeCLIProvider(Provider):
    """Usa o Claude Code instalado no container (`claude -p`), autenticado por
    CLAUDE_CODE_OAUTH_TOKEN (gerado com `claude setup-token`) ou ANTHROPIC_API_KEY."""

    name = "claude_cli"

    def structured(self, system, user, schema, model, effort):
        s = get_settings()
        with tempfile.TemporaryDirectory(prefix="acv-claude-") as tmp:
            sys_file = Path(tmp) / "system.md"
            sys_file.write_text(system, encoding="utf-8")
            cmd = [
                s.claude_cli_bin, "-p",
                "--output-format", "json",
                "--json-schema", json.dumps(schema.model_json_schema()),
                "--model", model,
                "--effort", effort,
                "--system-prompt-file", str(sys_file),
                "--tools", "",
                "--strict-mcp-config",
                "--no-session-persistence",
            ]
            env = dict(os.environ)
            try:
                proc = subprocess.run(
                    cmd, input=user, capture_output=True, text=True, encoding="utf-8",
                    cwd=tmp, env=env, timeout=s.claude_cli_timeout,
                )
            except FileNotFoundError:
                raise AIError(f"'{s.claude_cli_bin}' não encontrado. Instale o Claude Code no container.")
            except subprocess.TimeoutExpired:
                raise AIError("Claude Code passou do tempo limite")
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise AIError(f"Saída inválida do Claude Code (exit {proc.returncode}): {(proc.stderr or proc.stdout)[:500]}")
        if data.get("is_error") or proc.returncode != 0:
            raise AIError(f"Claude Code falhou: {str(data.get('result') or data.get('api_error_status'))[:500]}")
        payload = data.get("structured_output")
        if payload is None:
            try:
                payload = json.loads(data.get("result") or "")
            except json.JSONDecodeError:
                raise AIError("Claude Code não devolveu JSON estruturado")
        return schema.model_validate(payload)


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self):
        import anthropic

        self.client = anthropic.Anthropic()

    def structured(self, system, user, schema, model, effort):
        import anthropic

        try:
            resp = self.client.beta.messages.parse(
                model=model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                output_config={"effort": effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError as e:
            raise AIError(f"Limite de taxa da API: {e}")
        except anthropic.APIStatusError as e:
            raise AIError(f"API da Anthropic respondeu {e.status_code}: {e.message}")
        except anthropic.APIConnectionError as e:
            raise AIError(f"Sem conexão com a API da Anthropic: {e}")
        if resp.stop_reason == "refusal":
            raise AIError("O modelo recusou a requisição")
        if resp.stop_reason == "max_tokens":
            raise AIError("Resposta cortada por max_tokens")
        if resp.parsed_output is None:
            raise AIError("Resposta sem JSON estruturado")
        return resp.parsed_output


# ---------------------------------------------------------------- utilidades para JSON estruturado

def strict_json_schema(schema: type[BaseModel]) -> dict:
    """JSON Schema no formato 'strict' da OpenAI: todo objeto com additionalProperties=false e
    todas as chaves obrigatórias, sem 'default'. A saída continua validada pelo Pydantic."""
    data = schema.model_json_schema()

    def fix(node):
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            for v in node.values():
                fix(v)
        elif isinstance(node, list):
            for v in node:
                fix(v)

    fix(data)
    return data


def parse_json_text(text: str) -> dict:
    """Extrai o objeto JSON de uma resposta (tolera ```json ... ``` e texto em volta)."""
    t = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if fence:
        t = fence.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        a, b = t.find("{"), t.rfind("}")
        if a >= 0 and b > a:
            try:
                return json.loads(t[a:b + 1])
            except json.JSONDecodeError:
                pass
    raise AIError(f"A IA não devolveu JSON válido: {t[:300]}")


def _validate(schema: type[T], payload: dict) -> T:
    from pydantic import ValidationError

    try:
        return schema.model_validate(payload)
    except ValidationError as e:
        raise AIError(f"JSON fora do formato esperado: {str(e)[:400]}")


# ---------------------------------------------------------------- Codex CLI (OpenAI)

class CodexCLIProvider(Provider):
    """Usa o Codex CLI instalado (`codex exec`), com o login que você já tem (`codex login`)
    ou OPENAI_API_KEY. Roda em sandbox somente leitura e devolve JSON via --output-schema."""

    name = "codex_cli"

    def structured(self, system, user, schema, model, effort):
        s = get_settings()
        with tempfile.TemporaryDirectory(prefix="acv-codex-") as tmp:
            schema_file = Path(tmp) / "schema.json"
            schema_file.write_text(json.dumps(strict_json_schema(schema)), encoding="utf-8")
            out_file = Path(tmp) / "out.json"
            cmd = [
                s.codex_cli_bin, "exec",
                "--skip-git-repo-check", "--ephemeral",
                "--sandbox", "read-only",
                "--output-schema", str(schema_file),
                "--output-last-message", str(out_file),
                "-c", f"model_reasoning_effort={effort if effort in ('low', 'medium') else 'high'}",
            ]
            if model:
                cmd += ["--model", model]
            cmd.append("-")
            prompt = (
                f"<instrucoes>\n{system}\n</instrucoes>\n\n{user}\n\n"
                "Não rode comandos nem leia arquivos: responda só com o JSON pedido."
            )
            try:
                proc = subprocess.run(
                    cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                    cwd=tmp, timeout=s.ai_timeout,
                )
            except FileNotFoundError:
                raise AIError(f"'{s.codex_cli_bin}' não encontrado. Instale com: npm install -g @openai/codex")
            except subprocess.TimeoutExpired:
                raise AIError("Codex passou do tempo limite")
            if proc.returncode != 0 or not out_file.exists():
                raise AIError(f"Codex falhou (exit {proc.returncode}): {(proc.stderr or proc.stdout)[-500:]}")
            text = out_file.read_text(encoding="utf-8")
        return _validate(schema, parse_json_text(text))


# ---------------------------------------------------------------- APIs compatíveis com OpenAI

# provedor -> (URL base, variável da chave)
COMPAT_ENDPOINTS = {
    "openai": ("https://api.openai.com/v1", "openai_api_key"),
    "openrouter": ("https://openrouter.ai/api/v1", "openrouter_api_key"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini_api_key"),
    "ollama": ("http://localhost:11434/v1", ""),
    "compatible": ("", ""),
}


class OpenAICompatProvider(Provider):
    """Chat Completions no formato da OpenAI. Serve para OpenAI, OpenRouter, Gemini, Ollama,
    LM Studio, Groq, DeepSeek e qualquer servidor compatível. Pede JSON Schema; se o servidor
    não aceitar, cai para modo JSON simples, com o schema no prompt."""

    def __init__(self, name: str):
        s = get_settings()
        self.name = name
        base, key_field = COMPAT_ENDPOINTS.get(name, ("", ""))
        self.base_url = (s.ai_base_url or base).rstrip("/")
        if name == "ollama" and not s.ai_base_url and os.environ.get("OLLAMA_HOST"):
            self.base_url = os.environ["OLLAMA_HOST"].rstrip("/") + "/v1"
        self.api_key = s.ai_api_key or (getattr(s, key_field) if key_field else "") or "sem-chave"
        if not self.base_url:
            raise AIError("Defina AI_BASE_URL para AI_PROVIDER=compatible")
        self._mode = "json_schema"  # json_schema -> json_object -> text

    def _post(self, body: dict) -> dict:
        import httpx

        headers = {"Authorization": f"Bearer {self.api_key}"}
        if self.name == "openrouter":
            headers.update({"HTTP-Referer": "https://github.com/XiangBr/ai-job-finder", "X-Title": "AI Job Finder"})
        try:
            r = httpx.post(f"{self.base_url}/chat/completions", json=body, headers=headers,
                           timeout=get_settings().ai_timeout)
        except httpx.HTTPError as e:
            raise AIError(f"Sem conexão com {self.base_url}: {e}")
        if r.status_code >= 400:
            raise AIError(f"{self.name} respondeu {r.status_code}: {r.text[:500]}")
        return r.json()

    def structured(self, system, user, schema, model, effort):
        if not model:
            raise AIError("Defina AI_MODEL_TRIAGE e AI_MODEL_CV no .env para este provedor")
        json_schema = strict_json_schema(schema)
        schema_hint = (
            "\n\nResponda SOMENTE com um objeto JSON válido (sem texto antes ou depois) que siga este JSON Schema:\n"
            + json.dumps(json_schema, ensure_ascii=False)
        )
        erro_anterior = ""
        tentativa = 0
        while tentativa < 2:
            sys_text = system + ("" if self._mode == "json_schema" else schema_hint)
            msgs = [{"role": "system", "content": sys_text}, {"role": "user", "content": user}]
            if erro_anterior:
                msgs.append({"role": "user", "content": f"A resposta anterior foi rejeitada: {erro_anterior}. Corrija e devolva o JSON completo."})
            body = {"model": model, "messages": msgs}
            if self._mode == "json_schema":
                body["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": schema.__name__, "schema": json_schema, "strict": True},
                }
            elif self._mode == "json_object":
                body["response_format"] = {"type": "json_object"}
            try:
                data = self._post(body)
            except AIError as e:
                # 400/422 com response_format: o servidor pode não aceitar JSON Schema. Rebaixa o
                # modo (json_schema -> json_object -> só prompt) e tenta de novo. Fica salvo para as próximas.
                if self._mode != "text" and re.search(r"respondeu (400|422)", str(e)):
                    self._mode = "json_object" if self._mode == "json_schema" else "text"
                    log.info("%s recusou o formato; usando modo %s (%s)", self.name, self._mode, str(e)[:200])
                    continue
                raise
            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            if msg.get("refusal"):
                raise AIError(f"O modelo recusou: {msg['refusal'][:300]}")
            if choice.get("finish_reason") == "length":
                raise AIError("Resposta cortada pelo limite de tokens do modelo")
            try:
                return _validate(schema, parse_json_text(msg.get("content") or ""))
            except AIError as e:
                tentativa += 1
                erro_anterior = str(e)[:500]
                log.warning("%s: resposta inválida (tentativa %s): %s", self.name, tentativa, erro_anterior)
        raise AIError(f"{self.name} não devolveu JSON no formato esperado: {erro_anterior}")


# ---------------------------------------------------------------- mock (sem IA)

def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _words(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9+#]{3,}", _norm(t))}


def _all_facts(fatos: dict) -> list[tuple[str, str]]:
    out = []

    def walk(node):
        if isinstance(node, dict):
            if "id" in node:
                txt = " ".join(str(node.get(k, "")) for k in ("texto", "nome", "cargo", "empresa", "detalhes"))
                out.append((str(node["id"]), txt))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(fatos)
    return out


class MockProvider(Provider):
    """Heurística por sobreposição de palavras. Serve para testar o fluxo sem gastar IA."""

    name = "mock"

    def fill_filters(self, texto, form, historico):
        from ..filters_form import FiltrosIA

        f = form.model_copy(deep=True)
        f.observacoes = f"{f.observacoes}\n{texto}".strip()
        return FiltrosIA(filtros=f, resumo="(mock) texto adicionado às observações", perguntas=[]), "mock"

    def analyze_job(self, job, fatos_yaml, filtros_yaml, filtro_codigo):
        fatos = yaml.safe_load(fatos_yaml) or {}
        skills = [str(s.get("nome", "")) for s in fatos.get("skills", []) if isinstance(s, dict)]
        desc = _norm(f"{job.cargo} {job.descricao}")
        hits = [sk for sk in skills if sk and _norm(sk) in desc]
        score = min(95, 45 + 9 * len(hits))
        reqs = [
            Requisito(requisito=sk, tipo="obrigatorio", classificacao="forte", evidencia=f"skill {sk}", fatos_ids=[])
            for sk in hits
        ]
        a = Analise(
            veredito=filtro_codigo.get("veredito", "APROVADA"),
            score=score,
            problema_empregador=f"(mock) {job.cargo} em {job.empresa}",
            motivos=[f"Cita {h}" for h in hits[:3]] or ["(mock) poucas palavras em comum"],
            requisitos=reqs,
            lacunas=[],
            alertas=[x for x in filtro_codigo.get("alertas", []) if x != "salário a confirmar"],
            motivo_descarte="",
        )
        return a, "mock"

    def tailor_cv(self, job, fatos_yaml, cv_base_md, analise, feedback="", regras=""):
        fatos = yaml.safe_load(fatos_yaml) or {}
        facts = _all_facts(fatos)
        ver = []
        for line in cv_base_md.splitlines():
            if not line.strip().startswith("- "):
                continue
            bullet = line.strip()[2:]
            bw = _words(bullet)
            best = max(facts, key=lambda f: len(bw & _words(f[1])), default=None)
            ids = [best[0]] if best and len(bw & _words(best[1])) >= 2 else []
            ver.append(Veracidade(bullet=bullet, fatos_ids=ids))
        cv = CVAdaptado(
            idioma="pt",
            titulo_alvo=job.cargo,
            fio_narrativo="(mock) CV base sem adaptação",
            cv_md=cv_base_md,
            veracidade=ver,
            diff=["(mock) nenhuma mudança: provedor de teste"],
            lacunas=[],
            mensagem_recrutador=f"Oi! Vi a vaga de {job.cargo} na {job.empresa} e gostaria de conversar.",
            perguntas_entrevista=[],
            cobertura_palavras_chave="(mock)",
        )
        return cv, "mock"


_provider: Provider | None = None


def get_provider() -> Provider:
    global _provider
    if _provider is None:
        name = get_settings().ai_provider
        if name == "claude_cli":
            _provider = ClaudeCLIProvider()
        elif name == "anthropic":
            _provider = AnthropicProvider()
        elif name == "codex_cli":
            _provider = CodexCLIProvider()
        elif name in COMPAT_ENDPOINTS:
            _provider = OpenAICompatProvider(name)
        else:
            if name != "mock":
                log.warning("AI_PROVIDER desconhecido '%s'; usando mock", name)
            _provider = MockProvider()
        log.info("Provedor de IA: %s", _provider.name)
    return _provider
