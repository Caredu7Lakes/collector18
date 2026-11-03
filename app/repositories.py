from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contact, Indication, RawMessage


async def raw_exists(session: AsyncSession, wa_message_id: str | None) -> bool:
    if not wa_message_id:
        return False
    found = await session.scalar(
        select(RawMessage.id).where(RawMessage.wa_message_id == wa_message_id)
    )
    return found is not None


async def save_raw(session: AsyncSession, **kw) -> RawMessage:
    raw = RawMessage(**kw)
    session.add(raw)
    await session.flush()  # popula raw.id sem fechar a transação
    return raw


async def save_contact(session: AsyncSession, source_message_id: int, data: dict) -> Contact:
    contact = Contact(source_message_id=source_message_id, **data)
    session.add(contact)
    return contact


async def save_indication(session: AsyncSession, source_message_id: int, data: dict) -> Indication:
    ind = Indication(source_message_id=source_message_id, **data)
    session.add(ind)
    return ind
