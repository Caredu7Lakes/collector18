from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawMessage(Base):
    """Toda mensagem recebida do grupo — auditoria e reprocesso."""

    __tablename__ = "raw_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    wa_message_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    remote_jid: Mapped[str] = mapped_column(String(128), index=True)
    from_me: Mapped[bool] = mapped_column(Boolean, default=False)
    message_type: Mapped[str] = mapped_column(String(64))
    sender_name: Mapped[str | None] = mapped_column(String(256))
    payload_json: Mapped[dict] = mapped_column(JSONB)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Contact(Base):
    """Prestador vindo de um contactMessage (vCard)."""

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(256))
    phones: Mapped[list[str]] = mapped_column(ARRAY(String))
    business_name: Mapped[str | None] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text)
    source_message_id: Mapped[int] = mapped_column(ForeignKey("raw_messages.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Indication(Base):
    """Indicação extraída de mensagem de texto. Shape de export: Contato|Serviço|Telefone."""

    __tablename__ = "indications"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str | None] = mapped_column(String(256))   # Contato
    servico_termo: Mapped[str | None] = mapped_column(String(256))   # Serviço (texto livre)
    phone: Mapped[str | None] = mapped_column(String(32))            # Telefone
    is_indication: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    source_message_id: Mapped[int] = mapped_column(ForeignKey("raw_messages.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
