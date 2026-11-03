"""initial: raw_messages, contacts, indications

Revision ID: 0001
Revises:
Create Date: 2026-11-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("wa_message_id", sa.String(128), unique=True),
        sa.Column("remote_jid", sa.String(128), nullable=False, index=True),
        sa.Column("from_me", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("message_type", sa.String(64), nullable=False),
        sa.Column("sender_name", sa.String(256)),
        sa.Column("payload_json", postgresql.JSONB, nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("phones", postgresql.ARRAY(sa.String), nullable=False),
        sa.Column("business_name", sa.String(256)),
        sa.Column("description", sa.Text),
        sa.Column("source_message_id", sa.Integer, sa.ForeignKey("raw_messages.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "indications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("provider_name", sa.String(256)),
        sa.Column("servico_termo", sa.String(256)),
        sa.Column("phone", sa.String(32)),
        sa.Column("is_indication", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("confidence", sa.Float),
        sa.Column("source_message_id", sa.Integer, sa.ForeignKey("raw_messages.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("indications")
    op.drop_table("contacts")
    op.drop_table("raw_messages")
