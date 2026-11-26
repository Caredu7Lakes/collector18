"""Agendador in-stack do collector18 (serviço dedicado no compose).

Substitui o cron do host: a programação vive versionada aqui, os logs saem no
stdout (capturados pelo json-file driver com rotação, já configurado no compose) e
um replay de VM recria o agendamento junto com a stack — sem cron no host, sem
gravar em /var/log. Os jobs reaproveitam os run() de daily_export e purge_raw.

Roda como: python -m scripts.scheduler  (CMD do serviço 'scheduler').
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from scripts import daily_export, purge_raw

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("collector18.scheduler")

TZ = ZoneInfo("America/Sao_Paulo")


async def _guard(name: str, run: Callable[[], Awaitable[None]]) -> None:
    """Executa um job logando start/ok/falha. Erro de um job nunca derruba o loop."""
    logger.info("job %s: start", name)
    try:
        await run()
        logger.info("job %s: ok", name)
    except Exception:
        logger.exception("job %s: FALHOU", name)


async def _run_daily_export() -> None:
    await _guard("daily_export", daily_export.run)


async def _run_purge_raw() -> None:
    await _guard("purge_raw", purge_raw.run)


async def main() -> None:
    sched = AsyncIOScheduler(timezone=TZ)
    sched.add_job(_run_daily_export, CronTrigger(hour=23, minute=54, timezone=TZ), id="daily_export")
    sched.add_job(_run_purge_raw, CronTrigger(hour=3, minute=0, timezone=TZ), id="purge_raw")
    sched.start()
    logger.info("scheduler up — daily_export 23:54, purge_raw 03:00 (America/Sao_Paulo)")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
