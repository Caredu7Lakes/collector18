"""Handoff desacoplado para o Concierge do Moshe.

Exporta no MESMO shape que o import do Moshe lê (openpyxl): 1ª aba, cabeçalho na
linha 1, dados a partir da linha 2, colunas Contato | Serviço | Telefone. O Moshe
consome este XLSX pelo import existente (casar_segmento → concierge_prestador,
indicado_por=NULL). Nenhum acesso ao banco do Concierge.
"""

import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.export_builder import XLSX_MEDIA_TYPE, build_indicacoes_xlsx
from app.models import Contact, Indication
from app.security import require_export_auth

router = APIRouter(tags=["export"])


@router.get("/export/indicacoes.xlsx", dependencies=[Depends(require_export_auth)])
async def export_xlsx(session: AsyncSession = Depends(get_session)) -> StreamingResponse:
    inds = await session.scalars(select(Indication).where(Indication.is_indication.is_(True)))
    contacts = await session.scalars(select(Contact))
    data = build_indicacoes_xlsx(list(inds), list(contacts))
    return StreamingResponse(
        io.BytesIO(data),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": "attachment; filename=indicacoes_collector18.xlsx"},
    )
