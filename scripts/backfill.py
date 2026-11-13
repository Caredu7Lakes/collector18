"""Backfill one-shot do histórico do grupo até uma data de corte.

O webhook é forward-only; este script puxa o que a instância Evolution já capturou
via POST /chat/findMessages (janela messageTimestamp gte+lte, por remoteJid, paginado)
e injeta cada registro no MESMO pipeline do webhook (ingest_data) — idempotente pela
UNIQUE(wa_message_id), seguro re-rodar.

Limite (confirmado na fonte 2.3.7): findMessages só lê o que a instância tem no banco
dela. Para alcançar histórico profundo, ligar o full-history sync no pareamento.

Rodar de dentro da rede do compose:
    docker compose exec app python -m scripts.backfill
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import httpx

from app.db import _sessionmaker
from app.routers.webhook import ingest_data

logger = logging.getLogger("collector18.backfill")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

PAGE_SIZE = 100


def build_query(remote_jid: str, since: str, until: str, page: int, offset: int = PAGE_SIZE) -> dict:
    """Corpo do POST /chat/findMessages. gte e lte são ambos obrigatórios na 2.3.7."""
    return {
        "where": {
            "key": {"remoteJid": remote_jid},
            "messageTimestamp": {"gte": since, "lte": until},
        },
        "page": page,
        "offset": offset,
    }


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"faltando variável de ambiente obrigatória: {name}")
    return value


async def run() -> None:
    base_url = os.environ.get("EVOLUTION_BASE_URL", "http://collector18-evolution:8080").rstrip("/")
    api_key = _require("EVOLUTION_API_KEY")
    instance = _require("EVOLUTION_INSTANCE")
    remote_jid = _require("BACKFILL_GROUP_JID")
    since = os.environ.get("BACKFILL_SINCE", "2020-01-01T00:00:00Z")
    until = os.environ.get("BACKFILL_UNTIL", "2026-11-09T23:59:59Z")

    url = f"{base_url}/chat/findMessages/{instance}"
    headers = {"Content-Type": "application/json", "apikey": api_key}
    tally: dict[str, int] = {}

    async with httpx.AsyncClient(timeout=60) as http, _sessionmaker()() as session:
        page = 1
        while True:
            resp = await http.post(url, json=build_query(remote_jid, since, until, page), headers=headers)
            resp.raise_for_status()
            block = resp.json().get("messages") or {}
            records = block.get("records") or []
            if not records:
                break
            for rec in records:
                status = (await ingest_data(session, rec, raw_payload=rec))["status"]
                tally[status] = tally.get(status, 0) + 1
            logger.info("página %s/%s processada", page, block.get("pages"))
            if page >= (block.get("pages") or page):
                break
            page += 1

    logger.info("backfill concluído (até %s) — %s", until, tally)


if __name__ == "__main__":
    asyncio.run(run())
