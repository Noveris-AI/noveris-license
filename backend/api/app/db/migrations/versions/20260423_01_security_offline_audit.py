"""security offline audit hardening

Revision ID: 20260423_01_security_offline_audit
Revises:
Create Date: 2026-04-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260423_01_security_offline_audit"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "license_activations",
        sa.Column("lease_counter", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "license_leases",
        sa.Column("lease_sequence", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("license_key", sa.String(length=255), nullable=True),
        sa.Column("activation_id", sa.Uuid(), nullable=True),
        sa.Column("operator_id", sa.Uuid(), nullable=True),
        sa.Column("client_ip", sa.String(length=45), nullable=True),
        sa.Column("cluster_id", sa.String(length=128), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_event_created", "audit_logs", ["event_type", "created_at"], unique=False)
    op.create_index("ix_audit_logs_license_key", "audit_logs", ["license_key"], unique=False)
    op.create_index("ix_audit_logs_operator", "audit_logs", ["operator_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_operator", table_name="audit_logs")
    op.drop_index("ix_audit_logs_license_key", table_name="audit_logs")
    op.drop_index("ix_audit_logs_event_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_column("license_leases", "lease_sequence")
    op.drop_column("license_activations", "lease_counter")
