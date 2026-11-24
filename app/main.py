from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.routers import export, webhook

app = FastAPI(title="collector18", version="0.1.0")
app.include_router(webhook.router)
app.include_router(export.router)


@app.get("/health")
async def health() -> dict:
    """Liveness: o processo está no ar. Não toca dependências (barato, sempre 200)."""
    return {"status": "ok"}


@app.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict:
    """Readiness: o banco (Neon) responde. 503 se não — o HEALTHCHECK do container
    aponta para cá, então 'healthy' passa a significar 'consegue ingerir'."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="db unavailable") from exc
    return {"status": "ready"}