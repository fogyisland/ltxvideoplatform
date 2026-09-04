# app/db/models.py
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    admin = "admin"
    user = "user"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class JobStage(str, enum.Enum):
    loading_model = "loading_model"
    encoding = "encoding"
    denoising = "denoising"
    decoding = "decoding"
    writing = "writing"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.user)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Model(Base):
    __tablename__ = "models"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(32))  # t2v_distilled|t2v_full|i2v_long|lora
    checkpoint_path: Mapped[str] = mapped_column(String(512))
    config_path: Mapped[str] = mapped_column(String(512))
    default_steps: Mapped[int] = mapped_column(Integer, default=20)
    default_frames: Mapped[int] = mapped_column(Integer, default=121)
    vram_gb: Mapped[int] = mapped_column(Integer, default=16)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(Text, default="")


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # ULID
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("models.id"))
    params_json: Mapped[str] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.queued, index=True
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    stage: Mapped[JobStage] = mapped_column(Enum(JobStage), default=JobStage.loading_model)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    preview_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    parent_job_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Upload(Base):
    __tablename__ = "uploads"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    path: Mapped[str] = mapped_column(String(512))
    kind: Mapped[str] = mapped_column(String(32))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ProjectStatus(str, enum.Enum):
    draft = "draft"
    rendering = "rendering"
    done = "done"
    archived = "archived"


class SceneStatus(str, enum.Enum):
    draft = "draft"
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # ULID
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    style: Mapped[str] = mapped_column(String(32), default="Cinematic")
    model_id: Mapped[str] = mapped_column(String(64), default="ltx-13b-distilled-long-multi-shot")
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.draft)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    scenes: Mapped[list["Scene"]] = relationship(
        "Scene", backref="project", cascade="all, delete-orphan",
        order_by="Scene.position",
    )


class Scene(Base):
    __tablename__ = "scenes"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # ULID
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)  # 0..N-1
    prompt: Mapped[str] = mapped_column(Text, default="")
    image_upload_id: Mapped[str | None] = mapped_column(ForeignKey("uploads.id"), nullable=True)
    duration: Mapped[str] = mapped_column(String(16), default="medium")  # short/medium/long
    quality: Mapped[str] = mapped_column(String(16), default="standard")
    status: Mapped[SceneStatus] = mapped_column(Enum(SceneStatus), default=SceneStatus.draft)
    job_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
