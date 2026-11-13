"""Extractor: heurística, timeout/erro do LLM caindo no fallback, e métrica emitida."""

from types import SimpleNamespace

from app.services import extractor


def test_heuristica_detecta_indicacao_com_telefone():
    r = extractor._heuristic("contato do eletricista 11999998888")
    assert r["phone"] == "11999998888"
    assert r["is_indication"] is True
    assert r["confidence"] == 0.3


def test_heuristica_pedido_nao_e_indicacao():
    r = extractor._heuristic("alguém indica um eletricista? 11999998888")
    assert r["is_indication"] is False  # é pedido, não oferta


async def test_sem_chave_usa_heuristica(monkeypatch):
    monkeypatch.setattr(
        extractor,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key=None),
    )
    r = await extractor.extract("indico o alfaiate 11999998888")
    assert r["phone"] == "11999998888"
    assert r["is_indication"] is True


async def test_llm_falha_cai_no_fallback(monkeypatch):
    monkeypatch.setattr(
        extractor,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key="x", openai_model="m", openai_timeout_seconds=1.0),
    )

    class _FakeCompletions:
        async def create(self, **_kw):
            raise RuntimeError("timeout simulado")

    class _FakeClient:
        def __init__(self, *_a, **_k):
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr("openai.AsyncOpenAI", _FakeClient)

    r = await extractor.extract("indico o alfaiate 11999998888")  # não pode levantar
    assert r["phone"] == "11999998888"  # heurística assumiu
    assert r["is_indication"] is True


def test_metrica_emitida(monkeypatch, caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="collector18.extractor"):
        extractor._log_metric("heuristic", 0.0, extractor._heuristic("x 11999998888"))
    assert any("metric=extract" in m and "method=heuristic" in m for m in caplog.messages)
