"""add projects and scenes tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), index=True),
        sa.Column("title", sa.String(length=200)),
        sa.Column("style", sa.String(length=32), server_default="Cinematic"),
        sa.Column("model_id", sa.String(length=64), server_default="ltx-13b-distilled-long-multi-shot"),
        sa.Column("status", sa.Enum("draft", "rendering", "done", "archived", name="projectstatus"),
                  server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "scenes",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id"), index=True),
        sa.Column("position", sa.Integer(), server_default="0"),
        sa.Column("prompt", sa.Text(), server_default=""),
        sa.Column("image_upload_id", sa.String(length=32), sa.ForeignKey("uploads.id"), nullable=True),
        sa.Column("duration", sa.String(length=16), server_default="medium"),
        sa.Column("quality", sa.String(length=16), server_default="standard"),
        sa.Column("status", sa.Enum("draft", "queued", "running", "succeeded", "failed", "skipped",
                                     name="scenestatus"), server_default="draft"),
        sa.Column("job_id", sa.String(length=32), nullable=True),
        sa.Column("output_path", sa.String(length=512), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("scenes")
    op.drop_table("projects")