#!/usr/bin/env bash
# Deploy do collector18 na EC2 — invocado via SSM pelo job de CD.
# Só o app é reconstruído; Evolution/Postgres/Redis (sessão do WhatsApp) não são
# tocados. Migrations aplicadas de forma idempotente. O git (fetch + reset) é feito
# pelo CD ANTES de chamar este script, para que ele já esteja na versão mais nova.
set -euo pipefail

cd /home/ubuntu/collector18

docker compose up -d --build app scheduler
docker compose exec -T app alembic upgrade head
