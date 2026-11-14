"""Testes dos provedores de IA sem rede: o servidor compatível com OpenAI é simulado."""

import json

import httpx
import pytest

from app.ai import providers
from app.ai.providers import AIError, OpenAICompatProvider, parse_json_text, strict_json_schema
from app.ai.schemas import Analise, CVAdaptado
from app.config import get_settings

ANALISE = {
    "veredito": "APROVADA", "score": 82, "problema_empregador": "Automatizar relatórios",
    "motivos": ["Python", "LLMs", "Docker"], "requisitos": [], "lacunas": [], "alertas": [],
    "motivo_descarte": "",
}


def test_strict_schema_fecha_todos_os_objetos():
    for model in (Analise, CVAdaptado):
        schema = strict_json_schema(model)

        def walk(node):
            if isinstance(node, dict):
                if node.get("type") == "object" and "properties" in node:
                    assert node["additionalProperties"] is False
                    assert set(node["required"]) == set(node["properties"])
                assert "default" not in node
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(schema)


def test_parse_json_text_tolera_cercas_e_texto():
    assert parse_json_text('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_text('Claro! {"a": 2} espero ter ajudado') == {"a": 2}
    with pytest.raises(AIError):
        parse_json_text("sem json aqui")


class FakeServer:
    """Recusa response_format=json_schema (como alguns servidores locais) e responde JSON em cerca."""

    def __init__(self):
        self.calls = []

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.calls.append(json)
        fmt = (json.get("response_format") or {}).get("type")
        if fmt == "json_schema":
            return httpx.Response(400, text='{"error": "response_format json_schema not supported"}')
        content = "```json\n" + _dumps(ANALISE) + "\n```"
        return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": "stop"}]})


def _dumps(obj):
    return json.dumps(obj, ensure_ascii=False)


def test_compat_cai_para_json_object(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "ai_base_url", "http://fake/v1")
    server = FakeServer()
    monkeypatch.setattr(httpx, "post", server)
    p = OpenAICompatProvider("compatible")
    out = p.structured("sistema", "usuário", Analise, "modelo-x", "low")
    assert out.score == 82
    assert [c.get("response_format", {}).get("type") for c in server.calls] == ["json_schema", "json_object"]
    assert "JSON Schema" in server.calls[1]["messages"][0]["content"]  # schema vai no prompt no fallback


def test_compat_exige_modelo(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "ai_base_url", "http://fake/v1")
    with pytest.raises(AIError, match="AI_MODEL"):
        OpenAICompatProvider("compatible").structured("s", "u", Analise, "", "low")


def test_registro_de_provedores():
    assert set(providers.COMPAT_ENDPOINTS) >= {"openai", "openrouter", "gemini", "ollama", "compatible"}
