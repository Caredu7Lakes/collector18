"""Expurgo de retenção do raw_messages (minimização LGPD).

Remove as mensagens brutas (payload completo do WhatsApp — PII) com received_at mais
antigo que a janela de retenção (RAW_RETENTION_DAYS, default 90). O dado derivado
(contacts/indications) SOBREVIVE: a FK source_message_id é ON DELETE SET NULL, então
o produto permanece e só o vínculo de auditoria com o raw removido é desfeito.

Tradeoff: após o expurgo a mensagem bruta não é mais reprocessável/reclassificável —
a janela de retenção é também a janela de reprocesso.

Idempotente e seguro re-rodar. Rodar de dentro da rede do compose:
    docker compose exec -T app python -m scripts.purge_raw

Agendar (cron no host, diário às 03:00; redirecione a saída para um log):
    0 3 * * * cd /home/ubuntu/collector18 && docker compose exec -T app python -m scripts.purge_raw
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.config import get_settings
from app.db import _sessionmaker
from app.models import RawMessage

logger = logging.getLogger("collector18.purge_raw")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


def cutoff(now: datetime, retention_days: int) -> datetime:
    """Corte: raw com received_at ANTERIOR a este instante é expurgado."""
    return now - timedelta(days=retention_days)


async def run() -> None:
    retention_days = get_settings().raw_retention_days
    limit = cutoff(datetime.now(UTC), retention_days)

    async with _sessionmaker()() as session:
        result = await session.execute(delete(RawMessage).where(RawMessage.received_at < limit))
        await session.commit()
        logger.info(
            "expurgo concluído — %s raw removidos (retenção %sd, corte %s)",
            result.rowcount,
            retention_days,
            limit.isoformat(),
        )


if __name__ == "__main__":
    asyncio.run(run())
