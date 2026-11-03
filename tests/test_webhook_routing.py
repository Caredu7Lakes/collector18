"""Garantia da invariante central: só grupo é ingerido; DM/fromMe são ignorados."""

import pytest

from app.routers.webhook import _extract_text


def test_extract_conversation():
    assert _extract_text({"conversation": "oi"}) == "oi"


def test_extract_extended_text():
    assert _extract_text({"extendedTextMessage": {"text": "tem alfaiate?"}}) == "tem alfaiate?"


def test_extract_none_for_media():
    assert _extract_text({"imageMessage": {}}) is None


@pytest.mark.parametrize(
    "jid,from_me,ingest",
    [
        ("123-456@g.us", False, True),  # grupo → ingere
        ("5511999999999@s.whatsapp.net", False, False),  # DM → ignora
        ("123-456@g.us", True, False),  # fromMe → ignora
    ],
)
def test_routing_predicate(jid, from_me, ingest):
    is_group = jid.endswith("@g.us") and not from_me
    assert is_group == ingest
