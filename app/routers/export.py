"""Handoff desacoplado para o Concierge do Moshe.

Exporta no MESMO shape que o import do Moshe lê (openpyxl): 1ª aba, cabeçalho na
linha 1, dados a partir da linha 2, colunas Contato | Serviço | Telefone. O Moshe
consome este XLSX pelo import existente (casar_segmento → concierge_prestador,
indicado_por=NULL). Nenhum acesso ao banco do Concierge.
"""

import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Contact, Indication

router = APIRouter(tags=["export"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/export/indicacoes.xlsx")
async def export_xlsx(session: AsyncSession = Depends(get_session)) -> StreamingResponse:
    wb = Workbook()
    ws = wb.active
    ws.title = "Indicações"
    ws.append(["Contato", "Serviço", "Telefone"])  # cabeçalho (linha 1; import lê da 2)

    # Indicações de texto já classificadas como indicação.
    inds = await session.scalars(select(Indication).where(Indication.is_indication.is_(True)))
    for i in inds:
        ws.append([i.provider_name or "", i.servico_termo or "", i.phone or ""])

    # Contatos (vCard): não há termo de serviço — usa o nome comercial como Serviço
    # (o import casa por embedding e, se fraco, abriga em "Outros" com o texto como
    # descrição). Vários telefones seguem separados por ';' (o import faz o split).
    contacts = await session.scalars(select(Contact))
    for c in contacts:
        ws.append([c.display_name, c.business_name or "", ";".join(c.phones)])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": "attachment; filename=indicacoes_collector18.xlsx"},
    )
