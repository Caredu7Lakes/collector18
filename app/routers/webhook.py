"""Webhook da Evolution (messages.upsert).

Frente 1 (coletor) + Frente 2 (roteamento):
  - remote_jid termina em @g.us  → é grupo → INGERE e para. Nunca responde.
  - qualquer outra origem (DM)   → IGNORA no v0 (collector18 não atende ninguém).
O collector18 é receive-only: não há cliente de envio, por construção não responde grupo.

Durabilidade: o raw é COMITADO antes de qualquer enriquecimento (vCard/LLM). Uma
falha no enriquecimento nunca desfaz a ingestão nem força retry infinito da Evolution.

A ingestão de um evento vive em ingest_data(), reusada pelo webhook (fluxo novo) e
pelo backfill (histórico via findMessages) — mesmo pipeline, uma lógica só.
"""

import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError
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


async def ingest_data(session: AsyncSession, data: dict, raw_payload: dict) -> dict:
    """Ingere um evento da Evolution (o objeto `data`): roteia, grava o raw e enriquece.

    `data` traz key/message/messageType/pushName (shape igual no webhook e no
    findMessages). `raw_payload` é o que vai para auditoria em raw_messages — o body
    completo do webhook, ou o registro do findMessages no backfill.
    """
    key = data.get("key") or {}
    remote_jid = key.get("remote_jid") or key.get("remoteJid") or ""

    # Roteamento: só grupos. DM e fromMe são ignorados sem persistir.
    if not remote_jid.endswith("@g.us") or key.get("fromMe"):
        return {"status": "ignored"}

    allowed = get_settings().allowed_groups
    if allowed and remote_jid not in allowed:
        return {"status": "ignored"}

    # Idempotência (fast-path): evita o enriquecimento numa reentrega óbvia. A
    # garantia REAL é a UNIQUE(wa_message_id) no commit abaixo — este SELECT só
    # poupa trabalho; sozinho não cobre reentrega concorrente.
    if await raw_exists(session, key.get("id")):
        return {"status": "duplicate"}

    message = data.get("message") or {}
    message_type = data.get("messageType") or next(iter(message), "unknown")

    # 1) Durabilidade: grava e COMITA o raw antes de qualquer enriquecimento.
    #    Numa reentrega concorrente a 2ª inserção viola a UNIQUE(wa_message_id) e
    #    vira 'duplicate' — não 500 (que faria a Evolution re-tentar em loop).
    #    Sem key.id (wa_message_id nulo) não há colisão (NULL no UNIQUE) e a
    #    mensagem é ingerida sem dedup: aceitável, pois o upsert real sempre traz id.
    try:
        raw = await save_raw(
            session,
            wa_message_id=key.get("id"),
            remote_jid=remote_jid,
            from_me=bool(key.get("fromMe")),
            message_type=message_type,
            sender_name=data.get("pushName"),
            payload_json=raw_payload,
        )
        await session.commit()  # expire_on_commit=False → raw.id sobrevive
    except IntegrityError:
        await session.rollback()
        return {"status": "duplicate"}

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

    return await ingest_data(session, body.get("data") or {}, raw_payload=body)
