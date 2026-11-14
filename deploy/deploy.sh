#!/usr/bin/env bash
# Envia o código para a VPS e sobe com docker compose.
# Uso (Git Bash, na raiz do repo):  bash deploy/deploy.sh [host-ssh] [pasta-remota]
# O .env da VPS é criado à mão na primeira vez (ver README) e nunca é sobrescrito.
set -euo pipefail
HOST="${1:-vps}"
DIR="${2:-${DEPLOY_DIR:-/opt/ai-job-finder}}"
cd "$(dirname "$0")/.."

echo ">> enviando código para $HOST:$DIR"
ssh "$HOST" "mkdir -p $DIR"
tar --exclude=node_modules --exclude=.venv --exclude=__pycache__ --exclude=frontend/dist \
    --exclude=data --exclude=.env --exclude=.git \
    -czf - Dockerfile docker-compose.yml .dockerignore .env.example deploy backend frontend skills exemplos \
  | ssh "$HOST" "tar -xzf - -C $DIR"

echo ">> build e subida"
ssh "$HOST" "cd $DIR && test -f .env || { echo 'Falta $DIR/.env (copie de .env.example)'; exit 1; }"
ssh "$HOST" "cd $DIR && docker compose up -d --build app && docker compose ps"
echo ">> ok. Logs: ssh $HOST 'cd $DIR && docker compose logs -f app'"
