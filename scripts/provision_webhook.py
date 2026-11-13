"""Provisiona o webhook da instância Evolution (idempotente).

Substitui o passo manual do README. Registra, NA INSTÂNCIA Evolution, o webhook
apontando para o collector com o header Authorization: Bearer que o handler exige.

Na Evolution 2.3.7 (confirmado no código): o emit por instância depende só do array
`events` da própria instância (events=[MESSAGES_UPSERT]); o header customizado só
existe via config por instância — webhook global por .env não carrega header.

Rodar de dentro da rede do compose (onde a Evolution é alcançável):
    docker compose exec app python -m scripts.provision_webhook
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

EVENTS = ["MESSAGES_UPSERT"]


def build_payload(webhook_url: str, webhook_token: str) -> dict:
    """Corpo do POST /webhook/set/{instance} no shape aceito pela 2.3.7 (aninhado)."""
    return {
        "webhook": {
            "enabled": True,
            "url": webhook_url,
            "headers": {"Authorization": f"Bearer {webhook_token}"},
            "byEvents": False,
            "base64": False,
            "events": EVENTS,
        }
    }


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"faltando variável de ambiente obrigatória: {name}")
    return value


def main() -> None:
    base_url = os.environ.get("EVOLUTION_BASE_URL", "http://collector18-evolution:8080").rstrip("/")
    api_key = _require("EVOLUTION_API_KEY")
    instance = _require("EVOLUTION_INSTANCE")
    webhook_url = os.environ.get("WEBHOOK_URL", "http://collector18-app:8000/webhook")
    webhook_token = _require("WEBHOOK_TOKEN")

    payload = json.dumps(build_payload(webhook_url, webhook_token)).encode()
    req = urllib.request.Request(
        f"{base_url}/webhook/set/{instance}",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "apikey": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (URL interna do compose)
            print(f"webhook registrado na instância {instance} (HTTP {resp.status})")
            print(resp.read().decode())
    except urllib.error.HTTPError as exc:
        sys.exit(f"falha ao registrar webhook (HTTP {exc.code}): {exc.read().decode()}")
    except urllib.error.URLError as exc:
        sys.exit(f"Evolution inalcançável em {base_url}: {exc.reason}")


if __name__ == "__main__":
    main()
