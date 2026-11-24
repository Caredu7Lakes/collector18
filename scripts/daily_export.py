"""Export diário das indicações novas do dia → e-mail por SES (anexo XLSX).

Delta = registros com created_at >= início do dia (America/Sao_Paulo). Se não houver
nada novo, não envia (evita e-mail vazio). O tratamento humano e a ingestão/dedup
acontecem depois, no Moshe — este job só captura e entrega.

Agendar (cron no host, 23:54 Brasília; redirecione a saída para um log):
    CRON_TZ=America/Sao_Paulo
    54 23 * * * cd /home/ubuntu/collector18 && docker compose exec -T app python -m scripts.daily_export
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.db import _sessionmaker
from app.export_builder import build_indicacoes_xlsx
from app.repositories import contacts_since, indications_since
from app.ses_mailer import send_xlsx

logger = logging.getLogger("collector18.daily_export")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

TZ = ZoneInfo("America/Sao_Paulo")


def day_start(now: datetime) -> datetime:
    """Meia-noite do dia local (America/Sao_Paulo) de `now`."""
    return now.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)


async def run() -> None:
    since = day_start(datetime.now(TZ))
    async with _sessionmaker()() as session:
        inds = await indications_since(session, since)
        contacts = await contacts_since(session, since)

    if not inds and not contacts:
        logger.info("nada novo desde %s — e-mail nao enviado", since.isoformat())
        return

    xlsx = build_indicacoes_xlsx(inds, contacts)
    filename = f"indicacoes_{since:%Y%m%d}.xlsx"
    message_id = send_xlsx(
        subject=f"[collector18] Indicacoes novas {since:%d/%m/%Y}",
        body=(
            f"{len(inds)} indicacoes e {len(contacts)} contatos novos no dia. "
            "Arquivo em anexo para tratamento (ingestao/dedup no Moshe)."
        ),
        xlsx=xlsx,
        filename=filename,
    )
    logger.info("e-mail enviado (%s inds, %s contatos) MessageId=%s", len(inds), len(contacts), message_id)


if __name__ == "__main__":
    asyncio.run(run())
