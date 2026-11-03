"""Handoff desacoplado para o Concierge do Moshe.

Exporta no MESMO shape da planilha já importada: Contato | Serviço | Telefone.
O Moshe consome este CSV pelo import existente (casar_segmento → concierge_prestador,
indicado_por=NULL). Nenhum acesso ao banco do Concierge.
"""

import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Contact, Indication

router = APIRouter(tags=["export"])


@router.get("/export/indicacoes.csv")
async def export_csv(session: AsyncSession = Depends(get_session)) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Contato", "Serviço", "Telefone"])

    # Indicações de texto já classificadas como indicação
    inds = await session.scalars(select(Indication).where(Indication.is_indication.is_(True)))
    for i in inds:
        writer.writerow([i.provider_name or "", i.servico_termo or "", i.phone or ""])

    # Contatos (vCard): serviço fica vazio — o import casa pelo nome comercial/termo depois
    contacts = await session.scalars(select(Contact))
    for c in contacts:
        writer.writerow([c.display_name, c.business_name or "", ";".join(c.phones)])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=indicacoes_collector18.csv"},
    )
