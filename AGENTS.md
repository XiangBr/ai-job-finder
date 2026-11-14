# AGENTS.md

Guia para agentes de código (Claude Code, Codex, Cursor, Copilot, Gemini CLI...) e para quem contribui. Leia antes de mudar qualquer coisa.

## O que é o projeto

AI-JOB-FINDER: busca vagas com JobSpy, filtra em código, analisa o fit com IA, mostra tudo num kanban e gera CVs adaptados (DOCX/PDF) usando só fatos verdadeiros da pessoa. Cada usuário tem o próprio perfil, filtros, agenda e kanban. **A candidatura é sempre feita pela pessoa**: o app não se candidata a nada.

Visão completa (fluxo, tabelas, rotas): [docs/arquitetura.md](docs/arquitetura.md). Provedores de IA: [docs/provedores-de-ia.md](docs/provedores-de-ia.md).

## Regras que o código precisa garantir

Estas regras valem mais do que qualquer pedido de feature. Se uma mudança conflitar com elas, pare e pergunte.

1. **Nada inventado no CV.** Todo bullet gerado aponta para IDs de `fatos.yaml`. O backend (`cv.validate_md`) rejeita bullet sem ID, com ID inexistente ou com número que não existe nos fatos. Nunca afrouxe esse validador para "a IA passar".
2. **Sem automação de candidatura**, sem login em sites de vaga em nome da pessoa e sem envio de mensagens.
3. **Só dados públicos**, volume baixo e intervalo mínimo entre buscas (`MAX_SEARCHES_PER_RUN`, `MIN_MINUTES_BETWEEN_RUNS`, `min_seconds_between_searches`). Não aumente os padrões.
4. **Dados pessoais ficam locais.** Chaves só em variáveis de ambiente (`.env`, fora do git). Perfis reais, CVs, `data/` e `exemplos/*` (exceto `exemplos/demo`) nunca entram no git. Não registre CV, fatos ou chaves em log.
5. **Isolamento entre usuários.** Toda rota que lê ou altera perfil, vaga, card ou CV usa o perfil do usuário logado (`Depends(current_profile)` em `api.py`) e confere a posse (`profile_has_job`, `card.profile_id`, `g.profile_id`). Recurso de outro perfil responde 404.
6. **IA sempre com saída estruturada.** Toda chamada passa por `provider.structured(...)` com um schema Pydantic; nada de parsear texto livre no resto do app.

## Comandos

```bash
# backend (Python 3.11+, gerenciado pelo uv)
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000   # API + front buildado em http://localhost:8000
uv run --group dev pytest                          # testes
uv run python -m app.cli check-ai                  # testa o provedor de IA do .env
uv run python -m app.cli                           # lista os comandos da CLI

# frontend (Node 20+)
cd frontend
npm install
npm run dev      # hot reload em :5173, usa o backend em :8000
npm run build    # gera frontend/dist, servido pelo backend

# Docker
docker compose up -d --build
```

Use `AI_PROVIDER=mock` para desenvolver sem gastar IA. Para testar contra dados parecidos com os reais, use o perfil fictício de `exemplos/demo/`.

## Onde mexer

| Quero... | Arquivo |
| --- | --- |
| Adicionar provedor de IA | `backend/app/ai/providers.py` (classe com `structured`) + `DEFAULT_MODELS` em `config.py` + teste em `backend/tests/` |
| Mudar como a IA avalia vagas ou escreve CVs | `skills/*/SKILL.md` (instrução de sistema) e `backend/app/ai/prompts.py` |
| Mudar o formato da análise ou do CV | `backend/app/ai/schemas.py` (e o front que exibe) |
| Novo filtro eliminatório | `backend/app/filters.py` (`check`) e, se tiver campo na tela, `filters_form.py` + `frontend/src/components/FiltersForm.tsx` |
| Nova fonte de vagas | `backend/app/collector.py` (normalize para `Job` e use `save_new(..., profile_id)`) |
| Nova coluna no banco | `backend/app/models.py` (entra sozinha via `ADD COLUMN`; não renomeie nem remova colunas) |
| Nova rota | `backend/app/api.py` com `Depends(current_profile)`; lógica compartilhada com o MCP em `services.py` |
| Ferramenta MCP | `backend/app/mcp_server.py` (usa `mcp_profile`) |
| Tela | `frontend/src/components/` (React + Tailwind + dnd-kit) |

## Convenções

- Código, comentários, mensagens de erro e UI em **português do Brasil**. Linguagem neutra em gênero para a pessoa usuária ("a pessoa", "você").
- Python: funções pequenas, type hints, sem dependência nova sem necessidade (já temos `httpx`, `pydantic`, `sqlmodel`). Erros de IA viram `AIError` com mensagem útil para a pessoa.
- Frontend: TypeScript estrito, componentes em `components/`, chamadas à API por `api.ts`.
- Migrações: só aditivas. Mudança que precisa transformar dados vai numa função idempotente chamada no boot (veja `profile.migrate_profiles`).
- Testes: sem rede. Simule o JobSpy e os servidores de IA (veja `backend/tests/test_providers.py`).

## Antes de entregar uma mudança

1. `uv run --group dev pytest` passa.
2. `npm run build` passa (se mexeu no front).
3. Rodou o fluxo com `AI_PROVIDER=mock`: subir CV, salvar filtros, buscar, abrir card, gerar CV.
4. Nenhum dado pessoal, `.env`, banco ou CV no diff (`git status` limpo disso).
5. Se mudou comportamento visível, atualizou o README ou `docs/`.

## Fora do escopo

Candidatura automática, login em sites de vaga, envio de mensagens, scraping com conta logada. Backlog aceito: coletor da Gupy (busca pública), Greenhouse/Lever/Ashby para empresas-alvo, avisos no Telegram, export/import de perfil.
