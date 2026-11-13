"""Testes de integração do handler /webhook.

Cobrem as invariantes do núcleo sem banco: auth (401), roteamento (só @g.us),
idempotência (duplicate) e ordem de durabilidade (raw comitado antes do
enriquecimento). Repositórios e LLM são stubados; o foco é a lógica do handler.
"""

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from app.db import get_session
from app.main import app
from app.routers import webhook
from app.services import extractor

TOKEN = "test-token"  # casa com WEBHOOK_TOKEN do conftest
AUTH = {"Authorization": f"Bearer {TOKEN}"}
GROUP = "123-456@g.us"
DM = "5511999999999@s.whatsapp.net"


class DummySession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class Recorder:
    def __init__(self):
        self.saved_raw = False
        self.saved_contact = False
        self.saved_indication = False
        self.extracted = False


@pytest.fixture
def rec(monkeypatch):
    r = Recorder()
    session = DummySession()

    async def fake_get_session():
        yield session

    async def fake_raw_exists(_session, wa_id):
        return wa_id == "DUP"

    async def fake_save_raw(_session, **kw):
        r.saved_raw = True
        return type("Raw", (), {"id": 1})()

    async def fake_save_contact(_session, _rid, _data):
        r.saved_contact = True

    async def fake_save_indication(_session, _rid, _data):
        r.saved_indication = True

    async def fake_extract(_text):
        r.extracted = True
        return {
            "provider_name": None,
            "servico_termo": None,
            "phone": None,
            "is_indication": False,
            "confidence": 0.3,
        }

    app.dependency_overrides[get_session] = fake_get_session
    monkeypatch.setattr(webhook, "raw_exists", fake_raw_exists)
    monkeypatch.setattr(webhook, "save_raw", fake_save_raw)
    monkeypatch.setattr(webhook, "save_contact", fake_save_contact)
    monkeypatch.setattr(webhook, "save_indication", fake_save_indication)
    monkeypatch.setattr(extractor, "extract", fake_extract)
    yield r, session
    app.dependency_overrides.clear()


async def _post(body, headers=AUTH):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/webhook", json=body, headers=headers)


def _text_evt(jid=GROUP, wa_id="A1", from_me=False, text="indico o alfaiate 11999998888"):
    return {
        "data": {
            "key": {"remoteJid": jid, "id": wa_id, "fromMe": from_me},
            "message": {"conversation": text},
            "messageType": "conversation",
            "pushName": "Fulano",
        }
    }


async def test_sem_auth_401(rec):
    resp = await _post(_text_evt(), headers={})
    assert resp.status_code == 401


async def test_auth_errado_401(rec):
    resp = await _post(_text_evt(), headers={"Authorization": "Bearer errado"})
    assert resp.status_code == 401


async def test_dm_ignorada(rec):
    recorder, _ = rec
    resp = await _post(_text_evt(jid=DM))
    assert resp.json()["status"] == "ignored"
    assert recorder.saved_raw is False


async def test_from_me_ignorada(rec):
    recorder, _ = rec
    resp = await _post(_text_evt(from_me=True))
    assert resp.json()["status"] == "ignored"
    assert recorder.saved_raw is False


async def test_duplicata(rec):
    recorder, _ = rec
    resp = await _post(_text_evt(wa_id="DUP"))
    assert resp.json()["status"] == "duplicate"
    assert recorder.saved_raw is False


async def test_texto_ingerido_durabilidade(rec):
    recorder, session = rec
    resp = await _post(_text_evt())
    body = resp.json()
    assert body["status"] == "ingested"
    assert recorder.saved_raw is True  # raw gravado
    assert recorder.extracted is True  # LLM chamado
    assert recorder.saved_indication is True  # indicação gravada
    assert session.commits >= 2  # 1 do raw + 1 do enriquecimento


async def test_contact_message(rec):
    recorder, _ = rec
    evt = {
        "data": {
            "key": {"remoteJid": GROUP, "id": "C1", "fromMe": False},
            "message": {
                "contactMessage": {"displayName": "Zé", "vcard": "BEGIN:VCARD\nTEL:11999\nEND:VCARD"}
            },
            "messageType": "contactMessage",
            "pushName": "Zé",
        }
    }
    resp = await _post(evt)
    assert resp.json()["status"] == "ingested"
    assert recorder.saved_contact is True
    assert recorder.saved_indication is False


async def test_duplicata_concorrente_integrityerror(rec, monkeypatch):
    """Reentrega concorrente: a 2a insercao viola a UNIQUE -> 'duplicate', nao 500."""
    recorder, session = rec

    async def raise_conflict(_session, **kw):
        raise IntegrityError("INSERT INTO raw_messages", {}, Exception("duplicate key"))

    monkeypatch.setattr(webhook, "save_raw", raise_conflict)

    resp = await _post(_text_evt(wa_id="RACE"))
    assert resp.json()["status"] == "duplicate"
    assert recorder.saved_indication is False  # nao chega ao enriquecimento
    assert session.rollbacks >= 1
