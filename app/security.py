"""Autenticação Bearer dos endpoints internos do collector18.

Comparação em tempo constante (hmac.compare_digest) para não vazar o segredo por
canal de timing. Dependências separadas por fronteira de confiança: o webhook usa o
segredo compartilhado com a instância Evolution; o export usa o segredo do operador
que faz o handoff do XLSX. Tokens distintos = menor privilégio — o segredo da
Evolution não habilita exportar PII, e cada um rotaciona de forma isolada.
"""

import hmac

from fastapi import Header, HTTPException

from app.config import get_settings


def _check_bearer(authorization: str | None, expected_token: str) -> None:
    expected = f"Bearer {expected_token}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


async def require_webhook_auth(authorization: str | None = Header(default=None)) -> None:
    """Protege /webhook: Bearer == WEBHOOK_TOKEN (segredo da instância Evolution)."""
    _check_bearer(authorization, get_settings().webhook_token)


async def require_export_auth(authorization: str | None = Header(default=None)) -> None:
    """Protege /export/*: Bearer == EXPORT_TOKEN (segredo do operador do handoff)."""
    _check_bearer(authorization, get_settings().export_token)