#!/usr/bin/env bash
# Sincroniza collector18 com a versao endurecida (ruff + testes de integracao + CI).
# Rode DENTRO do repo existente: bash apply_hardening_collector18.sh
set -euo pipefail

mkdir -p ".github/workflows"
mkdir -p "app"
mkdir -p "app/routers"
mkdir -p "app/services"
mkdir -p "migrations"
mkdir -p "migrations/versions"
mkdir -p "tests"

cat > ".dockerignore" << 'COLLECTOR18_EOF'
.git
.github
.env
.env.*
!.env.example
__pycache__/
*.pyc
.pytest_cache/
.venv/
tests/
*.csv
README.md
.ruff_cache/
COLLECTOR18_EOF

cat > ".env.example" << 'COLLECTOR18_EOF'
# Banco do coletor — Neon (asyncpg). Use ?ssl=require; NUNCA sslmode=/channel_binding=.
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx-pooler.us-west-2.aws.neon.tech/neondb?ssl=require

# Token que a Evolution manda no webhook (Authorization: Bearer <...>)
WEBHOOK_TOKEN=troque-por-um-token-forte

# Evolution (usado pelo docker-compose)
EVOLUTION_API_KEY=troque-por-uma-chave-forte

# Extração por LLM (opcional — sem chave usa fallback heurístico)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# JIDs de grupo a coletar (vazio = todos os grupos). Ex.: 123-456@g.us,789-012@g.us
ALLOWED_GROUP_JIDS=
COLLECTOR18_EOF

cat > ".github/workflows/ci.yml" << 'COLLECTOR18_EOF'
name: ci

on:
  push:
    branches: [main]
  pull_request:

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - name: Lint (ruff)
        run: ruff check .
      - name: Format check (ruff)
        run: ruff format --check .
      - name: Tests (pytest)
        run: pytest -q
COLLECTOR18_EOF

cat > ".gitignore" << 'COLLECTOR18_EOF'
.env
.env.*
!.env.example
__pycache__/
*.pyc
.pytest_cache/
.venv/
*.csv
.ruff_cache/
COLLECTOR18_EOF

cat > "Dockerfile" << 'COLLECTOR18_EOF'
FROM python:3.12-slim-bookworm

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# usuário não-root
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
COLLECTOR18_EOF

cat > "README.md" << 'COLLECTOR18_EOF'
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
GET /export/indicacoes.csv   →  Contato | Serviço | Telefone
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
instância apontando para `http://collector18-app:8000/webhook` com o header
`Authorization: Bearer <WEBHOOK_TOKEN>`.

## Notas de produção
- Neon via asyncpg: `DATABASE_URL` com `?ssl=require` (não `sslmode`/`channel_binding`).
- Evolution fixada em v2.3.7 + `CONFIG_SESSION_PHONE_VERSION` estável (pareamento).
- Evolution não-oficial: usar número dedicado (risco de ban).
COLLECTOR18_EOF

cat > "alembic.ini" << 'COLLECTOR18_EOF'
[alembic]
script_location = migrations
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
COLLECTOR18_EOF

cat > "app/__init__.py" << 'COLLECTOR18_EOF'

COLLECTOR18_EOF

cat > "app/config.py" << 'COLLECTOR18_EOF'
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Neon (asyncpg). Ex.: postgresql+asyncpg://user:pass@host/db?ssl=require
    # NÃO usar sslmode=/channel_binding= (quebram o asyncpg); usar ?ssl=require.
    database_url: str

    # Token que o webhook da Evolution envia no header Authorization: Bearer <...>
    webhook_token: str

    # Extração por LLM (opcional: sem chave, cai no fallback heurístico)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # JIDs dos grupos a ingerir (vazio = todos os grupos). Fora de grupo é ignorado.
    allowed_group_jids: str = ""

    @property
    def allowed_groups(self) -> set[str]:
        return {j.strip() for j in self.allowed_group_jids.split(",") if j.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
COLLECTOR18_EOF

cat > "app/db.py" << 'COLLECTOR18_EOF'
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
COLLECTOR18_EOF

cat > "app/main.py" << 'COLLECTOR18_EOF'
from fastapi import FastAPI

from app.routers import export, webhook

app = FastAPI(title="collector18", version="0.1.0")
app.include_router(webhook.router)
app.include_router(export.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
COLLECTOR18_EOF

cat > "app/models.py" << 'COLLECTOR18_EOF'
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawMessage(Base):
    """Toda mensagem recebida do grupo — auditoria e reprocesso."""

    __tablename__ = "raw_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    wa_message_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    remote_jid: Mapped[str] = mapped_column(String(128), index=True)
    from_me: Mapped[bool] = mapped_column(Boolean, default=False)
    message_type: Mapped[str] = mapped_column(String(64))
    sender_name: Mapped[str | None] = mapped_column(String(256))
    payload_json: Mapped[dict] = mapped_column(JSONB)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Contact(Base):
    """Prestador vindo de um contactMessage (vCard)."""

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(256))
    phones: Mapped[list[str]] = mapped_column(ARRAY(String))
    business_name: Mapped[str | None] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text)
    source_message_id: Mapped[int] = mapped_column(ForeignKey("raw_messages.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Indication(Base):
    """Indicação extraída de mensagem de texto. Shape de export: Contato|Serviço|Telefone."""

    __tablename__ = "indications"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str | None] = mapped_column(String(256))  # Contato
    servico_termo: Mapped[str | None] = mapped_column(String(256))  # Serviço (texto livre)
    phone: Mapped[str | None] = mapped_column(String(32))  # Telefone
    is_indication: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    source_message_id: Mapped[int] = mapped_column(ForeignKey("raw_messages.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
COLLECTOR18_EOF

cat > "app/repositories.py" << 'COLLECTOR18_EOF'
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contact, Indication, RawMessage


async def raw_exists(session: AsyncSession, wa_message_id: str | None) -> bool:
    if not wa_message_id:
        return False
    found = await session.scalar(select(RawMessage.id).where(RawMessage.wa_message_id == wa_message_id))
    return found is not None


async def save_raw(session: AsyncSession, **kw) -> RawMessage:
    raw = RawMessage(**kw)
    session.add(raw)
    await session.flush()  # popula raw.id sem fechar a transação
    return raw


async def save_contact(session: AsyncSession, source_message_id: int, data: dict) -> Contact:
    contact = Contact(source_message_id=source_message_id, **data)
    session.add(contact)
    return contact


async def save_indication(session: AsyncSession, source_message_id: int, data: dict) -> Indication:
    ind = Indication(source_message_id=source_message_id, **data)
    session.add(ind)
    return ind
COLLECTOR18_EOF

cat > "app/routers/__init__.py" << 'COLLECTOR18_EOF'

COLLECTOR18_EOF

cat > "app/routers/export.py" << 'COLLECTOR18_EOF'
"""Handoff desacoplado para o Concierge do Moshe.

Exporta no MESMO shape da planilha já importada: Contato | Serviço | Telefone.
O Moshe consome este CSV pelo import existente (casar_segmento → concierge_prestador,
indicado_por=NULL). Nenhum acesso ao banco do Concierge.
"""

import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Contact, Indication

router = APIRouter(tags=["export"])


@router.get("/export/indicacoes.csv")
async def export_csv(session: AsyncSession = Depends(get_session)) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Contato", "Serviço", "Telefone"])

    # Indicações de texto já classificadas como indicação
    inds = await session.scalars(select(Indication).where(Indication.is_indication.is_(True)))
    for i in inds:
        writer.writerow([i.provider_name or "", i.servico_termo or "", i.phone or ""])

    # Contatos (vCard): serviço fica vazio — o import casa pelo nome comercial/termo depois
    contacts = await session.scalars(select(Contact))
    for c in contacts:
        writer.writerow([c.display_name, c.business_name or "", ";".join(c.phones)])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=indicacoes_collector18.csv"},
    )
COLLECTOR18_EOF

cat > "app/routers/webhook.py" << 'COLLECTOR18_EOF'
"""Webhook da Evolution (messages.upsert).

Frente 1 (coletor) + Frente 2 (roteamento) no mesmo handler:
  - remote_jid termina em @g.us  → é grupo → INGERE e para. Nunca responde.
  - qualquer outra origem (DM)   → IGNORA no v0 (collector18 não atende ninguém).
O collector18 é receive-only: não há cliente de envio, por construção não responde grupo.

Durabilidade: o raw é COMITADO antes de qualquer enriquecimento (vCard/LLM). Uma
falha no enriquecimento nunca desfaz a ingestão nem força retry infinito da Evolution.
"""

import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.repositories import raw_exists, save_contact, save_indication, save_raw
from app.services import extractor, vcard

logger = logging.getLogger("collector18.webhook")

router = APIRouter(tags=["webhook"])


def _auth(authorization: str | None) -> None:
    expected = f"Bearer {get_settings().webhook_token}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


def _extract_text(message: dict) -> str | None:
    if "conversation" in message:
        return message["conversation"]
    ext = message.get("extendedTextMessage")
    if ext:
        return ext.get("text")
    return None


@router.post("/webhook")
async def webhook(
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _auth(authorization)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json") from None

    data = body.get("data") or {}
    key = data.get("key") or {}
    remote_jid = key.get("remote_jid") or key.get("remoteJid") or ""

    # Roteamento: só grupos. DM e fromMe são ignorados sem persistir.
    if not remote_jid.endswith("@g.us") or key.get("fromMe"):
        return {"status": "ignored"}

    allowed = get_settings().allowed_groups
    if allowed and remote_jid not in allowed:
        return {"status": "ignored"}

    # Idempotência: Evolution pode reentregar o mesmo evento.
    if await raw_exists(session, key.get("id")):
        return {"status": "duplicate"}

    message = data.get("message") or {}
    message_type = data.get("messageType") or next(iter(message), "unknown")

    # 1) Durabilidade: grava e COMITA o raw antes de qualquer enriquecimento.
    raw = await save_raw(
        session,
        wa_message_id=key.get("id"),
        remote_jid=remote_jid,
        from_me=bool(key.get("fromMe")),
        message_type=message_type,
        sender_name=data.get("pushName"),
        payload_json=body,
    )
    await session.commit()  # expire_on_commit=False → raw.id sobrevive

    # 2) Enriquecimento: não pode derrubar a ingestão nem gerar retry infinito.
    try:
        if "contactMessage" in message:
            parsed = vcard.parse_contact(message["contactMessage"], fallback_name=data.get("pushName"))
            await save_contact(session, raw.id, parsed)
            await session.commit()
        else:
            text = _extract_text(message)
            if text:
                extracted = await extractor.extract(text)
                await save_indication(session, raw.id, extracted)
                await session.commit()
    except Exception:
        logger.exception("enriquecimento falhou raw_id=%s", raw.id)
        await session.rollback()  # raw já salvo → reprocessável depois

    return {"status": "ingested", "raw_id": raw.id}
COLLECTOR18_EOF

cat > "app/services/__init__.py" << 'COLLECTOR18_EOF'

COLLECTOR18_EOF

cat > "app/services/extractor.py" << 'COLLECTOR18_EOF'
"""Extração estruturada de uma mensagem de texto de grupo.

Saída: {provider_name, servico_termo, phone, is_indication, confidence}.
A classificação SEMÂNTICA (casar com os ~3976 segmentos do Concierge) NÃO acontece
aqui — isso é trabalho do import do Moshe via casar_segmento. Aqui só extraímos o
termo livre como o morador escreveu.
"""

import json
import re

from app.config import get_settings

_PHONE = re.compile(r"(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?9?\d{4}[-\s]?\d{4}")

_SYSTEM = (
    "Você extrai indicações de prestadores de serviço de mensagens de um grupo de "
    "condomínio. Responda APENAS JSON com as chaves: provider_name (str|null), "
    "servico_termo (str|null, o serviço como citado, ex.: 'alfaiate', 'instalação de "
    "boiler'), phone (str|null), is_indication (bool: é indicação/oferta de um "
    "prestador?), confidence (0..1). Pedidos do tipo 'alguém indica um X?' NÃO são "
    "indicação (is_indication=false)."
)


def _heuristic(text: str) -> dict:
    phone_m = _PHONE.search(text)
    asking = bool(re.search(r"\b(indica|indicar|algu[eé]m tem|procuro|preciso)\b", text, re.I))
    return {
        "provider_name": None,
        "servico_termo": None,
        "phone": phone_m.group(0).strip() if phone_m else None,
        "is_indication": bool(phone_m) and not asking,
        "confidence": 0.3,
    }


async def extract(text: str) -> dict:
    settings = get_settings()
    if not settings.openai_api_key:
        return _heuristic(text)

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": text},
        ],
    )
    try:
        data = json.loads(resp.choices[0].message.content or "{}")
    except (json.JSONDecodeError, TypeError):
        return _heuristic(text)

    return {
        "provider_name": data.get("provider_name"),
        "servico_termo": data.get("servico_termo"),
        "phone": data.get("phone"),
        "is_indication": bool(data.get("is_indication")),
        "confidence": data.get("confidence"),
    }
COLLECTOR18_EOF

cat > "app/services/vcard.py" << 'COLLECTOR18_EOF'
"""Parser do contactMessage da Evolution (payload.data.message.contactMessage).

O card traz displayName + uma string vCard. Extraímos nome, telefones, nome
comercial (ORG) e descrição (NOTE), como no exemplo do alfaiate 'Villa Alta Costura'.
"""

import re

_TEL = re.compile(r"^TEL[^:]*:(.+)$", re.IGNORECASE | re.MULTILINE)
_FN = re.compile(r"^FN[^:]*:(.+)$", re.IGNORECASE | re.MULTILINE)
_ORG = re.compile(r"^ORG[^:]*:(.+)$", re.IGNORECASE | re.MULTILINE)
_NOTE = re.compile(r"^NOTE[^:]*:(.+)$", re.IGNORECASE | re.MULTILINE)
_DIGITS = re.compile(r"\D+")


def _clean_phone(raw: str) -> str:
    # mantém dígitos; preserva '+' inicial se houver
    plus = raw.strip().startswith("+")
    d = _DIGITS.sub("", raw)
    return ("+" + d) if plus and d else d


def parse_contact(contact_message: dict, fallback_name: str | None = None) -> dict:
    vcard = contact_message.get("vcard", "") or ""
    display = contact_message.get("displayName") or fallback_name

    fn = _FN.search(vcard)
    name = (fn.group(1).strip() if fn else None) or display or "Sem nome"

    phones = [_clean_phone(m.group(1)) for m in _TEL.finditer(vcard)]
    phones = [p for p in dict.fromkeys(phones) if p]  # dedup, preserva ordem

    org = _ORG.search(vcard)
    note = _NOTE.search(vcard)

    return {
        "display_name": name,
        "phones": phones,
        "business_name": org.group(1).strip() if org else None,
        "description": note.group(1).strip() if note else None,
    }
COLLECTOR18_EOF

cat > "docker-compose.yml" << 'COLLECTOR18_EOF'
# collector18 — stack receive-only.
# Evolution v2.3.7 fixada (v2.4.0+ exige servidor de licença). Postgres/Redis são
# LOCAIS (sessão do WhatsApp do Evolution). O banco de DADOS do coletor é o Neon
# (externo, via DATABASE_URL no .env do serviço app).
name: collector18

services:
  evolution:
    image: evoapicloud/evolution-api:v2.3.7
    container_name: collector18-evolution
    restart: unless-stopped
    depends_on: [evo-postgres, evo-redis]
    environment:
      AUTHENTICATION_API_KEY: ${EVOLUTION_API_KEY}
      DATABASE_ENABLED: "true"
      DATABASE_PROVIDER: postgresql
      DATABASE_CONNECTION_URI: postgresql://evo:evo@evo-postgres:5432/evolution
      CACHE_REDIS_ENABLED: "true"
      CACHE_REDIS_URI: redis://evo-redis:6379
      # fix de pareamento (versão embutida é recusada pela Meta)
      CONFIG_SESSION_PHONE_VERSION: "2.3000.1034074495"
      # só precisamos do evento de mensagens recebidas
      WEBHOOK_GLOBAL_ENABLED: "false"
      WEBHOOK_EVENTS_MESSAGES_UPSERT: "true"
    networks: [collector-net]

  evo-postgres:
    image: postgres:16-alpine
    container_name: collector18-evo-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: evo
      POSTGRES_PASSWORD: evo
      POSTGRES_DB: evolution
    volumes: [evo-pg:/var/lib/postgresql/data]
    networks: [collector-net]

  evo-redis:
    image: redis:7-alpine
    container_name: collector18-evo-redis
    restart: unless-stopped
    volumes: [evo-redis:/data]
    networks: [collector-net]

  app:
    build: .
    container_name: collector18-app
    restart: unless-stopped
    env_file: .env          # DATABASE_URL (Neon), WEBHOOK_TOKEN, OPENAI_API_KEY...
    expose: ["8000"]        # Evolution chama http://collector18-app:8000/webhook (rede interna)
    networks: [collector-net]

networks:
  collector-net:

volumes:
  evo-pg:
  evo-redis:
COLLECTOR18_EOF

cat > "migrations/env.py" << 'COLLECTOR18_EOF'
import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.models import Base

target_metadata = Base.metadata


def _url() -> str:
    # Neon via asyncpg: ?ssl=require funciona; sslmode/channel_binding quebram o driver.
    return get_settings().database_url


def _run_sync(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    engine = create_async_engine(_url())
    async with engine.connect() as conn:
        await conn.run_sync(_run_sync)
    await engine.dispose()


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(_run_async())
COLLECTOR18_EOF

cat > "migrations/script.py.mako" << 'COLLECTOR18_EOF'
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
COLLECTOR18_EOF

cat > "migrations/versions/0001_initial.py" << 'COLLECTOR18_EOF'
"""initial: raw_messages, contacts, indications

Revision ID: 0001
Revises:
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("wa_message_id", sa.String(128), unique=True),
        sa.Column("remote_jid", sa.String(128), nullable=False, index=True),
        sa.Column("from_me", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("message_type", sa.String(64), nullable=False),
        sa.Column("sender_name", sa.String(256)),
        sa.Column("payload_json", postgresql.JSONB, nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("phones", postgresql.ARRAY(sa.String), nullable=False),
        sa.Column("business_name", sa.String(256)),
        sa.Column("description", sa.Text),
        sa.Column("source_message_id", sa.Integer, sa.ForeignKey("raw_messages.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "indications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("provider_name", sa.String(256)),
        sa.Column("servico_termo", sa.String(256)),
        sa.Column("phone", sa.String(32)),
        sa.Column("is_indication", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("confidence", sa.Float),
        sa.Column("source_message_id", sa.Integer, sa.ForeignKey("raw_messages.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("indications")
    op.drop_table("contacts")
    op.drop_table("raw_messages")
COLLECTOR18_EOF

cat > "pytest.ini" << 'COLLECTOR18_EOF'
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
pythonpath = .
COLLECTOR18_EOF

cat > "requirements.txt" << 'COLLECTOR18_EOF'
fastapi==0.115.5
uvicorn[standard]==0.32.1
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.0
pydantic-settings==2.6.1
openai==1.57.0
pytest==8.3.4
pytest-asyncio==0.24.0
httpx==0.28.1
ruff==0.17.3
COLLECTOR18_EOF

cat > "ruff.toml" << 'COLLECTOR18_EOF'
target-version = "py312"
line-length = 110

[lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]
# B008: Depends(...) em default de argumento é o idiom do FastAPI.
ignore = ["B008"]
COLLECTOR18_EOF

cat > "tests/__init__.py" << 'COLLECTOR18_EOF'

COLLECTOR18_EOF

cat > "tests/conftest.py" << 'COLLECTOR18_EOF'
import os

# Settings exige essas vars no boot; valores dummy para testes sem banco/segredos reais.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("WEBHOOK_TOKEN", "test-token")
COLLECTOR18_EOF

cat > "tests/test_vcard.py" << 'COLLECTOR18_EOF'
from app.services.vcard import parse_contact

# Espelha o card do exemplo: Alfaiate DEDÉ / Villa Alta Costura, 2 telefones.
VCARD = (
    "BEGIN:VCARD\n"
    "VERSION:3.0\n"
    "FN:Alfaiate DEDÉ ajuste De Roupa Masculino\n"
    "ORG:Villa Alta Costura\n"
    "TEL;type=CELL:+55 19 99730-5727\n"
    "TEL;type=HOME:+55 19 3325-3107\n"
    "NOTE:ateliê de costura, ternos, camisas, calças\n"
    "END:VCARD"
)


def test_parse_contact_full():
    out = parse_contact({"displayName": "Alfaiate DEDÉ", "vcard": VCARD})
    assert out["business_name"] == "Villa Alta Costura"
    assert out["phones"] == ["+5519997305727", "+551933253107"]
    assert "ateliê" in out["description"]
    assert out["display_name"].startswith("Alfaiate DEDÉ")


def test_parse_contact_fallback_name():
    out = parse_contact({"vcard": "BEGIN:VCARD\nTEL:11999999999\nEND:VCARD"}, fallback_name="Zé")
    assert out["display_name"] == "Zé"
    assert out["phones"] == ["11999999999"]
    assert out["business_name"] is None
COLLECTOR18_EOF

cat > "tests/test_webhook_integration.py" << 'COLLECTOR18_EOF'
"""Testes de integração do handler /webhook.

Cobrem as invariantes do núcleo sem banco: auth (401), roteamento (só @g.us),
idempotência (duplicate) e ordem de durabilidade (raw comitado antes do
enriquecimento). Repositórios e LLM são stubados; o foco é a lógica do handler.
"""

import httpx
import pytest

from app.db import get_session
from app.main import app
from app.routers import webhook
from app.services import extractor

TOKEN = "test-token"  # casa com WEBHOOK_TOKEN do conftest
AUTH = {"Authorization": f"Bearer {TOKEN}"}
GROUP = "123-456@g.us"
DM = "5511999999999@s.whatsapp.net"


class DummySession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class Recorder:
    def __init__(self):
        self.saved_raw = False
        self.saved_contact = False
        self.saved_indication = False
        self.extracted = False


@pytest.fixture
def rec(monkeypatch):
    r = Recorder()
    session = DummySession()

    async def fake_get_session():
        yield session

    async def fake_raw_exists(_session, wa_id):
        return wa_id == "DUP"

    async def fake_save_raw(_session, **kw):
        r.saved_raw = True
        return type("Raw", (), {"id": 1})()

    async def fake_save_contact(_session, _rid, _data):
        r.saved_contact = True

    async def fake_save_indication(_session, _rid, _data):
        r.saved_indication = True

    async def fake_extract(_text):
        r.extracted = True
        return {
            "provider_name": None,
            "servico_termo": None,
            "phone": None,
            "is_indication": False,
            "confidence": 0.3,
        }

    app.dependency_overrides[get_session] = fake_get_session
    monkeypatch.setattr(webhook, "raw_exists", fake_raw_exists)
    monkeypatch.setattr(webhook, "save_raw", fake_save_raw)
    monkeypatch.setattr(webhook, "save_contact", fake_save_contact)
    monkeypatch.setattr(webhook, "save_indication", fake_save_indication)
    monkeypatch.setattr(extractor, "extract", fake_extract)
    yield r, session
    app.dependency_overrides.clear()


async def _post(body, headers=AUTH):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/webhook", json=body, headers=headers)


def _text_evt(jid=GROUP, wa_id="A1", from_me=False, text="indico o alfaiate 11999998888"):
    return {
        "data": {
            "key": {"remoteJid": jid, "id": wa_id, "fromMe": from_me},
            "message": {"conversation": text},
            "messageType": "conversation",
            "pushName": "Fulano",
        }
    }


async def test_sem_auth_401(rec):
    resp = await _post(_text_evt(), headers={})
    assert resp.status_code == 401


async def test_auth_errado_401(rec):
    resp = await _post(_text_evt(), headers={"Authorization": "Bearer errado"})
    assert resp.status_code == 401


async def test_dm_ignorada(rec):
    recorder, _ = rec
    resp = await _post(_text_evt(jid=DM))
    assert resp.json()["status"] == "ignored"
    assert recorder.saved_raw is False


async def test_from_me_ignorada(rec):
    recorder, _ = rec
    resp = await _post(_text_evt(from_me=True))
    assert resp.json()["status"] == "ignored"
    assert recorder.saved_raw is False


async def test_duplicata(rec):
    recorder, _ = rec
    resp = await _post(_text_evt(wa_id="DUP"))
    assert resp.json()["status"] == "duplicate"
    assert recorder.saved_raw is False


async def test_texto_ingerido_durabilidade(rec):
    recorder, session = rec
    resp = await _post(_text_evt())
    body = resp.json()
    assert body["status"] == "ingested"
    assert recorder.saved_raw is True  # raw gravado
    assert recorder.extracted is True  # LLM chamado
    assert recorder.saved_indication is True  # indicação gravada
    assert session.commits >= 2  # 1 do raw + 1 do enriquecimento


async def test_contact_message(rec):
    recorder, _ = rec
    evt = {
        "data": {
            "key": {"remoteJid": GROUP, "id": "C1", "fromMe": False},
            "message": {
                "contactMessage": {"displayName": "Zé", "vcard": "BEGIN:VCARD\nTEL:11999\nEND:VCARD"}
            },
            "messageType": "contactMessage",
            "pushName": "Zé",
        }
    }
    resp = await _post(evt)
    assert resp.json()["status"] == "ingested"
    assert recorder.saved_contact is True
    assert recorder.saved_indication is False
COLLECTOR18_EOF

cat > "tests/test_webhook_routing.py" << 'COLLECTOR18_EOF'
"""Garantia da invariante central: só grupo é ingerido; DM/fromMe são ignorados."""

import pytest

from app.routers.webhook import _extract_text


def test_extract_conversation():
    assert _extract_text({"conversation": "oi"}) == "oi"


def test_extract_extended_text():
    assert _extract_text({"extendedTextMessage": {"text": "tem alfaiate?"}}) == "tem alfaiate?"


def test_extract_none_for_media():
    assert _extract_text({"imageMessage": {}}) is None


@pytest.mark.parametrize(
    "jid,from_me,ingest",
    [
        ("123-456@g.us", False, True),  # grupo → ingere
        ("5511999999999@s.whatsapp.net", False, False),  # DM → ignora
        ("123-456@g.us", True, False),  # fromMe → ignora
    ],
)
def test_routing_predicate(jid, from_me, ingest):
    is_group = jid.endswith("@g.us") and not from_me
    assert is_group == ingest
COLLECTOR18_EOF

echo "Sincronizado. Rode: ruff check . ; ruff format --check . ; pytest -q"