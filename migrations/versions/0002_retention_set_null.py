"""0002: retenção LGPD — source_message_id nullable + FK ON DELETE SET NULL

Habilita o expurgo de raw_messages antigo (minimização) SEM destruir o derivado:
a FK source_message_id→raw_messages passa a ON DELETE SET NULL e a coluna aceita
NULL. Assim o expurgo mantém contacts/indications (o produto) e só desfaz o vínculo
de auditoria com o raw removido.

O nome real da FK é refletido do banco (não assumido), pois no 0001 ela foi criada
inline no create_table e o nome é gerado pelo Postgres.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-24
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _fk_name(table: str) -> str:
    """Nome real da FK source_message_id→raw_messages na tabela (reflete, não assume)."""
    insp = inspect(op.get_bind())
    for fk in insp.get_foreign_keys(table):
        if fk["referred_table"] == "raw_messages" and "source_message_id" in fk["constrained_columns"]:
            return fk["name"]
    raise RuntimeError(f"FK source_message_id→raw_messages não encontrada em {table}")


def _set_fk(table: str, *, nullable: bool, ondelete: str | None) -> None:
    op.drop_constraint(_fk_name(table), table, type_="foreignkey")
    op.alter_column(table, "source_message_id", existing_type=sa.Integer(), nullable=nullable)
    op.create_foreign_key(
        f"{table}_source_message_id_fkey",
        table,
        "raw_messages",
        ["source_message_id"],
        ["id"],
        ondelete=ondelete,
    )


def upgrade() -> None:
    _set_fk("contacts", nullable=True, ondelete="SET NULL")
    _set_fk("indications", nullable=True, ondelete="SET NULL")


def downgrade() -> None:
    _set_fk("indications", nullable=False, ondelete=None)
    _set_fk("contacts", nullable=False, ondelete=None)
