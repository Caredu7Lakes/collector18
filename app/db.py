"""Sessão async do banco do coletor.

Engine e sessionmaker são criados sob demanda (lazy), não em import-time: importar
app.db — e tudo que o importa (webhook, export, main) — não exige mais DATABASE_URL
válido nem o driver asyncpg resolvível só para carregar o módulo. O engine nasce na
1ª sessão e é reusado (singleton via lru_cache).
"""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


@lru_cache(maxsize=1)
def _engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def _sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with _sessionmaker()() as session:
        yield session
