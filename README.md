# collector18

Serviço de ingestão assíncrona de mensagens de grupos de WhatsApp para construir uma
base estruturada de indicações de prestadores. Sistema **desacoplado** do Moshe:
repositório, instância Evolution, número e banco (Neon) próprios, sem acesso cruzado.

## Stack

FastAPI (async) · SQLAlchemy 2.0 async · PostgreSQL/Neon (asyncpg) · Alembic ·
Evolution API v2.3.7 · OpenAI (`gpt-4o-mini`) para extração estruturada.

## Arquitetura

Webhook `messages.upsert` → auth `Bearer` → roteamento por `remote_jid`: só `@g.us`
(grupo) é ingerido; DM e `fromMe` são descartados. É **receive-only** — não há cliente
de envio, logo, por construção, não há como responder o grupo.

Pipeline por tipo de mensagem:
- `contactMessage` → parsing de vCard (`FN/ORG/TEL/NOTE`) → `contacts`.
- texto → extração por LLM (termo de serviço + nome + telefone + `is_indication`),
  com fallback heurístico por regex quando não há chave ou o LLM falha → `indications`.

Toda mensagem crua é persistida em `raw_messages` (JSONB) para auditoria/reprocesso.

## Robustez e observabilidade

- **Durabilidade:** o `raw` é comitado **antes** de qualquer enriquecimento (vCard/LLM).
  Uma falha no enriquecimento nunca desfaz a ingestão nem força retry infinito da
  Evolution — o registro cru fica reprocessável.
- **Idempotência:** `UNIQUE(wa_message_id)`; reentrega (inclusive concorrente) vira
  `duplicate` via `IntegrityError`, não `500`.
- **Extração resiliente:** chamada ao LLM com timeout; qualquer erro degrada para a
  heurística. Cada extração emite uma métrica grepável
  (`metric=extract method=… latency_ms=… is_indication=… confidence=…`), base para
  p50/p95 e taxa de fallback.
- **Health:** `/health` (liveness, barato) e `/ready` (readiness — faz `SELECT 1` no
  Neon, 503 se o banco cair). O `HEALTHCHECK` do container aponta para `/ready`, então
  `healthy` significa "consegue ingerir".

## Segurança

- `/webhook` e `/export` exigem `Bearer`, com comparação em tempo constante
  (`hmac.compare_digest`).
- **Tokens separados por fronteira de confiança** (menor privilégio): `WEBHOOK_TOKEN`
  (segredo da instância Evolution) e `EXPORT_TOKEN` (segredo do operador do handoff) —
  o segredo de um não habilita o outro.

## Retenção / LGPD

O payload cru contém dados pessoais. `scripts/purge_raw` expurga `raw_messages`
anterior à janela de retenção (`RAW_RETENTION_DAYS`, default 90), agendado via cron. O
dado derivado (`contacts`/`indications`) sobrevive: a FK `source_message_id` é
`ON DELETE SET NULL`. A janela de retenção é também a janela de reprocesso.

## Handoff com o Concierge (Moshe)

A classificação semântica contra a taxonomia de segmentos do Concierge **não** ocorre
aqui — é feita no import do Moshe (`casar_segmento`, match por embedding). O collector18
só exporta no shape já consumido por aquele import:

```
GET /export/indicacoes.xlsx  →  Contato | Serviço | Telefone  (openpyxl)
```

## CI/CD

GitHub Actions em toda push:
- **quality:** `ruff check` + `ruff format --check` + `pytest`.
- **audit:** `pip-audit` sobre o `requirements.txt` (barra dependência com CVE conhecido).
- **deploy** (gated nos dois, só na branch de produção): deploy na EC2 via **AWS SSM
  `send-command`**, autenticado por **GitHub OIDC** — sem chave estática no CI e sem
  porta de entrada aberta no host (SSM é outbound). A confiança da role é travada no
  repo (IDs imutáveis) + branch.

Barreira local: `pre-commit` (`ruff` + newline/whitespace) — `pip install pre-commit && pre-commit install`.

## Rodar

```bash
cp .env.example .env     # DATABASE_URL (Neon), WEBHOOK_TOKEN, EXPORT_TOKEN, EVOLUTION_API_KEY
alembic upgrade head     # schema no Neon
docker compose up -d     # Evolution + Redis + Postgres(sessão) + app
pytest -q                # testes
```

Após subir: parear o WhatsApp (QR via API da Evolution) e registrar o webhook da
instância (passo versionado, idempotente):

```bash
docker compose exec app python -m scripts.provision_webhook
```

### Backfill (histórico)

O webhook é forward-only. Para trazer o histórico do grupo até uma data de corte (reusa
o mesmo pipeline; idempotente pela `UNIQUE(wa_message_id)`):

```bash
docker compose exec app python -m scripts.backfill
```

Controlado por `BACKFILL_GROUP_JID`, `BACKFILL_SINCE`, `BACKFILL_UNTIL`. Só alcança o
que a instância Evolution já capturou — ligar o full-history sync no pareamento para
histórico profundo.

## Notas de produção

- Neon via asyncpg: `DATABASE_URL` com `?ssl=require` (não `sslmode`/`channel_binding`).
- Evolution fixada em v2.3.7 + `CONFIG_SESSION_PHONE_VERSION` estável (pareamento).
- Evolution não-oficial: usar número dedicado (risco de ban).
