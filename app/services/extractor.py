"""Extração estruturada de uma mensagem de texto de grupo.

Saída: {provider_name, servico_termo, phone, is_indication, confidence}.
A classificação SEMÂNTICA (casar com os ~3976 segmentos do Concierge) NÃO acontece
aqui — isso é trabalho do import do Moshe via casar_segmento. Aqui só extraímos o
termo livre como o morador escreveu.
"""

import json
import re

from app.config import get_settings

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


async def extract(text: str) -> dict:
    settings = get_settings()
    if not settings.openai_api_key:
        return _heuristic(text)

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": text},
        ],
    )
    try:
        data = json.loads(resp.choices[0].message.content or "{}")
    except (json.JSONDecodeError, TypeError):
        return _heuristic(text)

    return {
        "provider_name": data.get("provider_name"),
        "servico_termo": data.get("servico_termo"),
        "phone": data.get("phone"),
        "is_indication": bool(data.get("is_indication")),
        "confidence": data.get("confidence"),
    }
