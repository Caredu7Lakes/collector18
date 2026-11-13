"""Extração estruturada de uma mensagem de texto de grupo.

Saída: {provider_name, servico_termo, phone, is_indication, confidence}.
A classificação SEMÂNTICA (casar com os ~3976 segmentos do Concierge) NÃO acontece
aqui — isso é trabalho do import do Moshe via casar_segmento. Aqui só extraímos o
termo livre como o morador escreveu.

Robustez: a chamada ao LLM tem timeout e QUALQUER falha (timeout, erro de API, JSON
inválido) cai no fallback heurístico — nunca derruba a ingestão. Cada extração emite
uma métrica grepável (latência + método) para medir p50/p95 e taxa de fallback.
"""

import json
import logging
import re
import time

from app.config import get_settings

logger = logging.getLogger("collector18.extractor")

_PHONE = re.compile(r"(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?9?\d{4}[-\s]?\d{4}")

_SYSTEM = (
    "Você extrai indicações de prestadores de serviço de mensagens de um grupo de "
    "condomínio. Responda APENAS JSON com as chaves: provider_name (str|null), "
    "servico_termo (str|null, o serviço como citado, ex.: 'alfaiate', 'instalação de "
    "boiler'), phone (str|null), is_indication (bool: é indicação/oferta de um "
    "prestador?), confidence (0..1). Pedidos do tipo 'alguém indica um X?' NÃO são "
    "indicação (is_indication=false)."
)


def _heuristic(text: str) -> dict:
    phone_m = _PHONE.search(text)
    asking = bool(re.search(r"\b(indica|indicar|algu[eé]m tem|procuro|preciso)\b", text, re.I))
    return {
        "provider_name": None,
        "servico_termo": None,
        "phone": phone_m.group(0).strip() if phone_m else None,
        "is_indication": bool(phone_m) and not asking,
        "confidence": 0.3,
    }


def _normalize(data: dict) -> dict:
    return {
        "provider_name": data.get("provider_name"),
        "servico_termo": data.get("servico_termo"),
        "phone": data.get("phone"),
        "is_indication": bool(data.get("is_indication")),
        "confidence": data.get("confidence"),
    }


def _log_metric(method: str, started: float, result: dict) -> None:
    # Linha única grepável (grep 'metric=extract'): base p/ p50/p95 e taxa de fallback.
    logger.info(
        "metric=extract method=%s latency_ms=%.1f is_indication=%s confidence=%s",
        method,
        (time.perf_counter() - started) * 1000,
        result["is_indication"],
        result["confidence"],
    )


async def extract(text: str) -> dict:
    started = time.perf_counter()
    settings = get_settings()

    if not settings.openai_api_key:
        result = _heuristic(text)
        _log_metric("heuristic", started, result)
        return result

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": text},
            ],
        )
        result = _normalize(json.loads(resp.choices[0].message.content or "{}"))
        method = "llm"
    except Exception:
        # Timeout, erro de API ou JSON inválido: degrada p/ heurística, não perde a
        # indicação nem força retry infinito da Evolution.
        logger.warning("extract LLM falhou — fallback heurístico", exc_info=True)
        result = _heuristic(text)
        method = "llm_fallback"

    _log_metric(method, started, result)
    return result
