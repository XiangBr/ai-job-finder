# Provedores de IA

O app usa IA em quatro momentos:

| Momento | Quando roda | Modelo usado |
| --- | --- | --- |
| Pré-análise da vaga (score, motivos, lacunas) | Toda vaga que passa nos filtros em código | `AI_MODEL_TRIAGE` |
| Leitura do CV e chat do currículo | Quando você sobe o CV ou conversa sobre ele | `AI_MODEL_CV` |
| CV adaptado e ajustes por chat | Quando você clica em "Gerar CV adaptado" | `AI_MODEL_CV` |
| Preencher filtros a partir do texto | Quando você usa o chat dos filtros | `AI_MODEL_TRIAGE` |

A triagem é o que mais gasta (uma chamada por vaga nova), então vale um modelo rápido e barato. O CV é raro e merece o melhor modelo que você tiver.

Todas as respostas são JSON validado por schema (Pydantic). Se a IA devolver algo fora do formato, o app tenta de novo ou mostra o erro; nunca grava lixo.

Para trocar de provedor, mude `AI_PROVIDER` no `.env` e reinicie o backend. Depois rode:

```bash
cd backend && uv run python -m app.cli check-ai
# Docker: docker compose exec app python -m app.cli check-ai
```

Se `AI_MODEL_TRIAGE` e `AI_MODEL_CV` ficarem vazios, o app usa os padrões de cada provedor (tabela `DEFAULT_MODELS` em [`backend/app/config.py`](../backend/app/config.py)). Nomes de modelo mudam rápido: se um padrão sair do ar, defina o atual no `.env`.

---

## Claude Code (`claude_cli`): usa a sua assinatura do Claude

Bom para quem já paga Claude Pro ou Max. O app chama o `claude -p` sem ferramentas, com a skill como system prompt e saída validada por JSON Schema.

**No seu computador:** instale e faça login uma vez.

```bash
npm install -g @anthropic-ai/claude-code
claude          # faça login e saia
```

```ini
AI_PROVIDER=claude_cli
# padrões: AI_MODEL_TRIAGE=claude-sonnet-5-5  AI_MODEL_CV=claude-opus-5-5
```

**No Docker ou numa VPS:** o container não tem o seu login. Gere um token de longa duração na sua máquina e cole no `.env`:

```bash
claude setup-token
```

```ini
CLAUDE_CODE_OAUTH_TOKEN=cole-aqui
```

A imagem Docker já vem com o Claude Code (`AI_CLIS=claude`, o padrão).

## Codex CLI (`codex_cli`): usa a sua assinatura do ChatGPT

Bom para quem já paga ChatGPT Plus ou Pro. O app chama `codex exec` em sandbox somente leitura, com `--output-schema` para garantir o JSON.

```bash
npm install -g @openai/codex
codex login
```

```ini
AI_PROVIDER=codex_cli
# vazio = o modelo do seu ~/.codex/config.toml. Para fixar: AI_MODEL_TRIAGE=... AI_MODEL_CV=...
```

**No Docker:** construa a imagem com o Codex e faça o login dentro do container:

```bash
AI_CLIS="claude codex" docker compose up -d --build
docker compose exec app codex login --device-auth
```

O login fica em `/home/app/.codex` dentro do container. Se recriar o container, faça login de novo (ou use `OPENAI_API_KEY`, que o Codex também aceita).

> O `codex_cli` foi testado rodando direto no computador. Dentro do Docker ele é experimental: o sandbox do Codex usa recursos do kernel que alguns hosts bloqueiam em containers. Se der erro de sandbox, prefira `openai` com chave de API no Docker.

## API da Anthropic (`anthropic`)

```ini
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

Usa structured outputs do SDK oficial. Chave em [console.anthropic.com](https://console.anthropic.com/).

## API da OpenAI (`openai`)

```ini
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
# padrões: gpt-5-mini (triagem) e gpt-5 (CV)
```

## OpenRouter (`openrouter`): centenas de modelos com uma chave

Bom para comparar modelos (Claude, GPT, Gemini, Llama, Qwen, DeepSeek...) sem abrir conta em cada empresa.

```ini
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...
AI_MODEL_TRIAGE=openai/gpt-5-mini
AI_MODEL_CV=anthropic/claude-sonnet-5.5
```

Os nomes ficam em [openrouter.ai/models](https://openrouter.ai/models). Prefira modelos com suporte a *structured outputs*; se o modelo não tiver, o app cai para modo JSON com o schema no prompt.

## Google Gemini (`gemini`)

```ini
AI_PROVIDER=gemini
GEMINI_API_KEY=...
# padrões: gemini-2.5-flash (triagem) e gemini-2.5-pro (CV)
```

Chave grátis (com limites) no [Google AI Studio](https://aistudio.google.com/apikey). Usa o endpoint compatível com OpenAI do Gemini.

## Ollama (`ollama`): 100% local, grátis e offline

```bash
# instale em https://ollama.com e baixe os modelos
ollama pull qwen3:8b
ollama pull qwen3:14b
```

```ini
AI_PROVIDER=ollama
AI_MODEL_TRIAGE=qwen3:8b
AI_MODEL_CV=qwen3:14b
```

- O app fala com `http://localhost:11434/v1`. Ollama em outra máquina: `AI_BASE_URL=http://IP:11434/v1` (ou a variável `OLLAMA_HOST`).
- App no Docker e Ollama no seu computador: `AI_BASE_URL=http://host.docker.internal:11434/v1`.
- Modelos pequenos (até 8B) servem para a triagem, mas erram mais no CV adaptado. Para o CV, use o maior que a sua máquina aguentar.
- O tempo de resposta depende do seu hardware: a primeira busca pode demorar.

## Qualquer API compatível com OpenAI (`compatible`)

LM Studio, Groq, DeepSeek, Together, Mistral, vLLM, LiteLLM...

```ini
AI_PROVIDER=compatible
AI_BASE_URL=http://localhost:1234/v1     # LM Studio, por exemplo
AI_API_KEY=                               # se o servidor pedir
AI_MODEL_TRIAGE=nome-do-modelo
AI_MODEL_CV=nome-do-modelo
```

O app tenta primeiro `response_format: json_schema`. Se o servidor recusar, tenta `json_object` e, por fim, só o schema no prompt. A validação acontece sempre do nosso lado.

## Sem IA (`mock`)

Heurística por palavras em comum entre a vaga e as skills do perfil. Serve para testar o fluxo e a interface sem gastar nada.

---

## Adicionar um provedor novo

Todos os provedores implementam um único método em [`backend/app/ai/providers.py`](../backend/app/ai/providers.py):

```python
class MeuProvider(Provider):
    name = "meu"

    def structured(self, system: str, user: str, schema: type[T], model: str, effort: str) -> T:
        # chame a sua IA com `system` + `user`, peça JSON no formato `schema.model_json_schema()`
        # (ou strict_json_schema(schema)) e devolva schema.model_validate(json)
        ...
```

Depois registre em `get_provider()`, adicione os modelos padrão em `DEFAULT_MODELS` (`config.py`) e um teste em `backend/tests/`. As funções `parse_json_text` e `strict_json_schema` ajudam com modelos que respondem JSON dentro de texto.
