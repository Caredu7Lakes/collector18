"""Export XLSX no shape que o import do Moshe lê: Contato | Serviço | Telefone.

Sessão stubada (sem banco): valida cabeçalho na linha 1, dados a partir da linha 2
e o join de múltiplos telefones por ';'.
"""

import io
from types import SimpleNamespace

import httpx
from openpyxl import load_workbook

from app.db import get_session
from app.main import app

AUTH = {"Authorization": "Bearer test-token"}


class FakeScalars:
    def __init__(self, items):
        self._items = items

    def __iter__(self):
        return iter(self._items)


class FakeSession:
    """scalars() na ORDEM do handler: 1ª chamada = indicações, 2ª = contatos."""

    def __init__(self, inds, contacts):
        self._results = [inds, contacts]
        self._i = 0

    async def scalars(self, _stmt):
        result = self._results[self._i]
        self._i += 1
        return FakeScalars(result)


async def _get_xlsx(session):
    async def fake_get_session():
        yield session

    app.dependency_overrides[get_session] = fake_get_session
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/export/indicacoes.xlsx", headers=AUTH)
    finally:
        app.dependency_overrides.clear()

async def _get_xlsx_raw(headers):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/export/indicacoes.xlsx", headers=headers)


async def test_export_sem_auth_401():
    resp = await _get_xlsx_raw({})
    assert resp.status_code == 401


async def test_export_auth_errado_401():
    resp = await _get_xlsx_raw({"Authorization": "Bearer errado"})
    assert resp.status_code == 401


async def test_export_xlsx_shape():
    inds = [SimpleNamespace(provider_name="Alfaiate João", servico_termo="alfaiate", phone="5511999998888")]
    contacts = [
        SimpleNamespace(
            display_name="Marcenaria Silva",
            business_name="Marcenaria",
            phones=["5511888887777", "1140001000"],
        )
    ]
    resp = await _get_xlsx(FakeSession(inds, contacts))
    assert resp.status_code == 200

    ws = load_workbook(io.BytesIO(resp.content)).active
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == ("Contato", "Serviço", "Telefone")
    assert rows[1] == ("Alfaiate João", "alfaiate", "5511999998888")
    assert rows[2] == ("Marcenaria Silva", "Marcenaria", "5511888887777;1140001000")
