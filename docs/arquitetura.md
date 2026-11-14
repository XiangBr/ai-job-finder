# Como funciona por dentro

## Visão geral

```
backend/app/
├── main.py           FastAPI: sobe banco, usuários, migração, agenda e MCP; serve o front em produção
├── api.py            rotas /api (cada rota usa o perfil do usuário logado)
├── auth.py           login com cookie assinado (itsdangerous) e senha bcrypt
├── models.py         tabelas SQLModel
├── db.py             SQLite em WAL + migração simples (ADD COLUMN)
├── profile.py        perfil por usuário, vínculo vaga↔perfil, perfil de exemplo
├── collector.py      JobSpy: plano de buscas, normalização, deduplicação
├── filters.py        filtros eliminatórios em código + tag de fit
├── filters_form.py   filtros.yaml <-> formulário da tela + preenchimento por IA
├── pipeline.py       execução: coleta -> filtros -> IA -> card no kanban
├── scheduler.py      APScheduler: a cada 5 min vê quais perfis estão na hora
├── services.py       quadro, detalhe da vaga, mover card (usado pela API e pelo MCP)
├── cv_import.py      extrai texto do CV (PDF/DOCX/DOC) e monta fatos + CV base com IA
├── cv_chat.py        chat do currículo (atualiza fatos e CV base)
├── cv.py             CV adaptado, validador de veracidade, DOCX/PDF, ajustes por chat
├── mcp_server.py     servidor MCP (Streamable HTTP em /mcp)
├── cli.py            comandos de terminal
└── ai/
    ├── providers.py  provedores de IA (interface única `structured`)
    ├── prompts.py    montagem dos prompts de análise e CV
    └── schemas.py    formatos de saída da IA (Pydantic)
skills/
├── cv-diagnostico-e-perfil/SKILL.md   onboarding: diagnóstico, entrevista, CV base, filtros
└── cv-adaptar-vaga/SKILL.md           análise de fit e CV adaptado por vaga
```

## Fluxo de uma execução

1. O `scheduler` acorda a cada 5 minutos e, para cada perfil com filtros e agenda ativa, vê se já passou o intervalo (padrão: o `frequencia_alerta` do filtros.yaml, editável na tela). "Buscar agora" pula essa espera.
2. `collector.build_plan` monta uma busca por **título × local** a partir do `filtros.yaml`, intercalando as áreas (1º título de cada área, depois o 2º...). Cada execução faz no máximo `MAX_SEARCHES_PER_RUN` buscas e continua de onde parou na próxima (rodízio pelo `cursor` da agenda).
3. Cada vaga é deduplicada por URL e por hash de empresa + cargo + local. A tabela `jobs` é global; a tabela `profile_jobs` registra qual perfil encontrou qual vaga. Assim dois usuários que acham a mesma vaga não duplicam nada, e cada um só vê as suas.
4. `filters.check` aplica os eliminatórios em código: título excluído, palavras proibidas, salário abaixo do mínimo, modelo de trabalho, empresa bloqueada. Reprovou: vai para **Descartadas** com o motivo, sem gastar IA.
5. As que passam vão para `provider.analyze_job` com o `fatos.yaml`, o `filtros.yaml` e a skill `cv-adaptar-vaga` (passos 1 a 3) como instrução. A resposta tem veredito, score, motivos, matriz de requisitos e lacunas.
6. Score ≥ 80 vira 🔥 Quente, 65 a 79 Morna, 50 a 64 Fria; abaixo de 50 vai para Descartadas. Bloqueios revisáveis (ex.: pede 2 anos e você tem 1) ficam em Selecionadas com o badge **alerta**.
7. A análise fica em cache pelo hash da vaga + fatos + filtros + modelo. Mudou o perfil, a vaga é reanalisada na próxima vez.

## CV adaptado e veracidade

- `cv.tailor` manda a vaga, os fatos, o CV base, a pré-análise e as suas regras de escrita para a IA (skill `cv-adaptar-vaga`, passos 4 a 6).
- A IA devolve o CV em markdown e uma **tabela de veracidade**: para cada bullet, os IDs de `fatos.yaml` que o sustentam.
- O validador remove bullets sem ID, com ID inexistente ou com números que não aparecem no `fatos.yaml`. O que foi removido aparece no painel.
- O DOCX sai pelo python-docx (uma coluna, texto selecionável, amigável a ATS); o PDF pelo LibreOffice.
- "Ajustar este CV com a IA" cria uma versão nova a cada pedido. O validador roda de novo em cada versão.

## Currículo

Aba **Currículo e filtros → Currículo**: envie PDF, DOCX ou DOC (DOC/ODT/RTF são convertidos pelo LibreOffice). Dois modos:

- **Otimizar com IA** (padrão): a IA aplica a skill `cv-diagnostico-e-perfil` e monta o banco de fatos, um CV base reescrito, as 5 correções de maior impacto e as perguntas para completar os números.
- **Usar como está**: o texto do arquivo vira o CV base sem reescrita. A IA monta só o banco de fatos.

Nada é salvo antes de clicar em "Salvar no perfil". PDF escaneado (imagem) é recusado com uma explicação. O arquivo original fica em `data/uploads/<id do perfil>/`.

O chat **"Converse sobre o seu CV"** atualiza fatos e CV base: fato informado vira `fonte: entrevista`, `status: confirmado`. Pedidos que exigem inventar ("coloca que eu liderei") não são aplicados; a IA pergunta se é verdade.

**Minhas regras para o CV**: texto livre ("resumo com 2 linhas", "não usar a fórmula XYZ"). Entram em todo CV adaptado, com prioridade sobre as técnicas de estilo da skill, mas nunca sobre a veracidade.

## Filtros

A aba **Filtros** mostra o `filtros.yaml` como formulário, com um chat no topo: você descreve o que procura e a IA preenche os campos. O YAML continua editável na aba avançada; chaves que o formulário não conhece são preservadas. Veja um exemplo completo em [`exemplos/demo/filtros.yaml`](../exemplos/demo/filtros.yaml).

## Modelo de dados

| Tabela | O que guarda |
| --- | --- |
| `users` | login (bcrypt) |
| `profiles` | um por usuário: `fatos_yaml`, `cv_base_md`, `filtros_yaml`, `regras_cv` |
| `schedules` | intervalo, ativo, última execução e cursor do rodízio, por perfil |
| `runs` | cada execução: buscas, encontradas, novas, analisadas, log |
| `jobs` | vagas (globais, deduplicadas) |
| `profile_jobs` | qual perfil encontrou qual vaga |
| `analyses` | pré-análise por vaga + perfil (score, tag, motivos, requisitos, lacunas, alertas) |
| `cards` | coluna e posição no kanban, notas, prazo |
| `card_events` | histórico de movimentação |
| `generated_cvs` | versões do CV adaptado, relatório, validação |

Colunas novas nos modelos entram sozinhas no boot (`db._add_missing_columns`, só `ADD COLUMN`). Bancos da versão antiga (um perfil só) são migrados no boot: o perfil existente vai para `LEGACY_PROFILE_OWNER` (ou o primeiro usuário).

## API

| Rota | O que faz |
| --- | --- |
| `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` | sessão |
| `GET/PUT /api/profile` | perfil do usuário logado |
| `POST /api/profile/cv-upload` | envia o CV e devolve a prévia (não salva) |
| `POST /api/profile/cv-chat` | chat do currículo (não salva) |
| `GET/PUT /api/filters`, `GET/PUT /api/filters/form`, `POST /api/filters/ai-fill` | filtros |
| `GET/PUT /api/schedule` | agenda |
| `POST /api/runs`, `GET /api/runs` | buscar agora e histórico |
| `GET /api/board`, `PATCH /api/cards/{id}` | kanban |
| `GET /api/jobs/{id}`, `POST /api/jobs/manual`, `POST /api/jobs/{id}/analyze` | vagas |
| `POST /api/jobs/{id}/tailor-cv`, `GET /api/cvs/{id}`, `POST /api/cvs/{id}/chat`, `GET /api/cvs/{id}/download?format=docx\|pdf\|md` | CV adaptado |

## Deploy numa VPS

Pré-requisitos: Docker com o plugin compose, acesso SSH (ex.: um host `vps` no `~/.ssh/config`) e um domínio apontando para a VPS.

1. Na VPS, crie `/opt/ai-job-finder/.env` a partir do `.env.example`, com `SECRET_KEY`, `BOOTSTRAP_USERS`, o provedor de IA, `COOKIE_SECURE=true` e `DOMAIN`.
2. Do seu PC (Git Bash ou terminal Linux/macOS), na raiz do repo:
   ```bash
   bash deploy/deploy.sh vps                 # pasta padrão /opt/ai-job-finder
   bash deploy/deploy.sh vps /outra/pasta    # ou escolha a pasta
   ```
   O script envia o código por `tar` + `ssh` (sem o `.env` e sem `data/`) e roda `docker compose up -d --build app`.
3. HTTPS:
   - Portas 80/443 livres: `docker compose --profile caddy up -d`. O Caddy emite o certificado para `DOMAIN`.
   - Já existe um proxy (nginx, Traefik, Caddy) em Docker: use o override [`deploy/docker-compose.vps.yml`](../deploy/docker-compose.vps.yml) para entrar na rede dele e aponte o domínio para `CONTAINER_NAME:8000`. Desative timeout curto em `/api/jobs/*/tailor-cv` (pode levar 2 a 3 min).

Backup do banco: `docker compose cp app:/app/data ./backup-data`. Para uma cópia consistente com o app rodando, use a API de backup do SQLite:

```bash
docker compose exec app python -c "import sqlite3;s=sqlite3.connect('/app/data/app.db');d=sqlite3.connect('/app/data/app-backup.db');s.backup(d)"
```
