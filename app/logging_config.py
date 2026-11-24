"""Configuração de logging da app.

Uvicorn não configura os loggers 'collector18.*'; por padrão o root fica em WARNING,
então as linhas INFO — inclusive a métrica do extractor (`metric=extract …`) — seriam
descartadas. Aqui anexamos um handler em stdout no nível LOG_LEVEL (default INFO) ao
namespace 'collector18'. A propagação fica no default (True): o uvicorn não instala
handler no root, então não há duplicação, e o caplog dos testes captura normalmente.
"""

import logging
import os


def configure_logging() -> None:
    logger = logging.getLogger("collector18")
    if logger.handlers:  # idempotente (import múltiplo nos testes)
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
