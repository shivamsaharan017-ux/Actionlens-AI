"""Add private in-workspace reminders."""
from alembic import op
import sqlalchemy as sa

revision = "0002_reminders"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    # The initial prototype migration uses Base.metadata.create_all, which may
    # already have created this table on a fresh install.
    inspector = sa.inspect(op.get_bind())
    if "reminders" not in inspector.get_table_names():
        op.create_table(
            "reminders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("notice_id", sa.Integer(), sa.ForeignKey("notices.id", ondelete="SET NULL"), nullable=True),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("reminder_date", sa.Date(), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
    inspector = sa.inspect(op.get_bind())
    existing = inspector.get_indexes("reminders") if "reminders" in inspector.get_table_names() else []
    for name, column in (("ix_reminders_user_id", "user_id"), ("ix_reminders_notice_id", "notice_id"), ("ix_reminders_reminder_date", "reminder_date")):
        if not any(item.get("name") == name for item in existing):
            op.create_index(name, "reminders", [column])


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if "reminders" in inspector.get_table_names():
        for name in ("ix_reminders_reminder_date", "ix_reminders_notice_id", "ix_reminders_user_id"):
            if any(item.get("name") == name for item in inspector.get_indexes("reminders")):
                op.drop_index(name, table_name="reminders")
        op.drop_table("reminders")
