# collector18

Serviço de ingestão assíncrona de mensagens de grupos de WhatsApp para construir uma
base de indicações de prestadores. Sistema **desacoplado** do Moshe: repositório,
instância Evolution, número e banco (Neon) próprios.

## Stack
FastAPI (async) · SQLAlchemy 2.0 async · PostgreSQL/Neon (asyncpg) · Alembic ·
Evolution API v2.3.7 · OpenAI (`gpt-4o-mini`) para extração estruturada.

## Arquitetura
Webhook `messages.upsert` → autenticação `Bearer` (`hmac.compare_digest`) → roteamento
por `remote_jid`: só `@g.us` (grupo) é ingerido; DM e `fromMe` são descartados. É
**receive-only** — não há cliente de envio, logo não há como responder o grupo.

Pipeline por tipo de mensagem:
- `contactMessage` → parsing de vCard (`FN/ORG/TEL/NOTE`) → `contacts`.
- texto → extração por LLM (termo de serviço + nome + telefone + `is_indication`),
  com fallback heurístico por regex quando não há chave. Resultado em `indications`.

Toda mensagem crua é persistida em `raw_messages` (JSONB) para auditoria/reprocesso.

## Handoff com o Concierge (Moshe)
A classificação semântica contra a taxonomia de segmentos do Concierge **não** ocorre
aqui — é feita no import do Moshe (`casar_segmento`, match por embedding). O collector18
só exporta no shape já consumido por aquele import:

```
GET /export/indicacoes.xlsx  →  Contato | Serviço | Telefone  (openpyxl, consumido pelo import do Moshe)
```

Sem acesso cruzado a bancos.

## Rodar
```bash
cp .env.example .env            # preencher DATABASE_URL (Neon), WEBHOOK_TOKEN, EVOLUTION_API_KEY
alembic upgrade head            # schema no Neon
docker compose up -d            # Evolution + Redis + Postgres(sessão) + app
pytest -q                       # testes
```

Após subir: parear o WhatsApp (QR via API da Evolution) e registrar o webhook da
instância (passo versionado, idempotente — não editar à mão):

```bash
docker compose exec app python -m scripts.provision_webhook
```

Registra o webhook da instância apontando para `WEBHOOK_URL` com o header
`Authorization: Bearer <WEBHOOK_TOKEN>` e `events:[MESSAGES_UPSERT]`.

## Notas de produção
- Neon via asyncpg: `DATABASE_URL` com `?ssl=require` (não `sslmode`/`channel_binding`).
- Evolution fixada em v2.3.7 + `CONFIG_SESSION_PHONE_VERSION` estável (pareamento).
- Evolution não-oficial: usar número dedicado (risco de ban).
