"""O namespace 'collector18' emite INFO (senão a métrica do extractor some em produção)."""

import logging

import app.main  # noqa: F401 — importar a app dispara configure_logging()


def test_namespace_collector18_em_info_com_handler():
    logger = logging.getLogger("collector18")
    assert logger.level == logging.INFO
    assert logger.handlers  # tem handler próprio em stdout


def test_metrica_do_extractor_e_emitida(caplog):
    with caplog.at_level(logging.INFO, logger="collector18.extractor"):
        logging.getLogger("collector18.extractor").info("metric=extract method=heuristic latency_ms=1.0")
    assert any("metric=extract" in m for m in caplog.messages)
