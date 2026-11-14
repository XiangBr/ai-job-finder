# ---- build do front
FROM node:22-bookworm-slim AS front
WORKDIR /front
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM node:22-bookworm-slim AS node
FROM ghcr.io/astral-sh/uv:0.11.16 AS uv

# ---- runtime: Python + Node (para os CLIs de IA) + LibreOffice (PDF)
FROM python:3.12-slim-bookworm
# CLIs de IA instalados na imagem: "claude", "codex", "claude codex" ou "" (nenhum, se usar só APIs)
ARG AI_CLIS="claude"
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN apt-get update \
 && apt-get install -y --no-install-recommends libreoffice-writer-nogui fonts-liberation fonts-dejavu-core ca-certificates tini \
 && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && for cli in $AI_CLIS; do \
      case "$cli" in \
        claude) npm install -g @anthropic-ai/claude-code && claude --version ;; \
        codex)  npm install -g @openai/codex && codex --version ;; \
      esac; \
    done

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --python /usr/local/bin/python3
COPY backend/app ./app
COPY skills /app/skills
COPY --from=front /front/dist /app/frontend/dist

RUN useradd -m -u 1000 app && mkdir -p /app/data && chown -R app:app /app/data
USER app
ENV HOME=/home/app PATH="/app/backend/.venv/bin:$PATH"
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
