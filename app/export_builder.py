"""Montagem do XLSX de indicações — shape Contato | Serviço | Telefone.

Função única usada pelo endpoint /export e pelo job diário (scripts/daily_export),
para não duplicar o formato que o import do Moshe consome (openpyxl, cabeçalho na
linha 1, dados a partir da linha 2).
"""

import io
from collections.abc import Iterable

from app.models import Contact, Indication

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def build_indicacoes_xlsx(indications: Iterable[Indication], contacts: Iterable[Contact]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Indicações"
    ws.append(["Contato", "Serviço", "Telefone"])  # cabeçalho (import lê da linha 2)

    for i in indications:
        ws.append([i.provider_name or "", i.servico_termo or "", i.phone or ""])

    # vCard: sem termo de serviço — usa o nome comercial; telefones unidos por ';'.
    for c in contacts:
        ws.append([c.display_name, c.business_name or "", ";".join(c.phones)])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
