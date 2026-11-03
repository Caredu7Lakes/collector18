from fastapi import FastAPI

from app.routers import export, webhook

app = FastAPI(title="collector18", version="0.1.0")
app.include_router(webhook.router)
app.include_router(export.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
