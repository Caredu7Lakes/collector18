"""Liveness (/health, sem banco) e readiness (/ready, pinga o banco)."""

import httpx
from sqlalchemy.exc import OperationalError

from app.db import get_session
from app.main import app


async def _get(path, session=None):
    if session is not None:

        async def fake():
            yield session

        app.dependency_overrides[get_session] = fake
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)
    finally:
        app.dependency_overrides.clear()


class _OkSession:
    async def execute(self, _stmt):
        return None


class _BrokenSession:
    async def execute(self, _stmt):
        raise OperationalError("SELECT 1", {}, Exception("conn refused"))


async def test_health_liveness_sem_banco():
    resp = await _get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_ready_ok():
    resp = await _get("/ready", _OkSession())
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


async def test_ready_banco_fora_503():
    resp = await _get("/ready", _BrokenSession())
    assert resp.status_code == 503
