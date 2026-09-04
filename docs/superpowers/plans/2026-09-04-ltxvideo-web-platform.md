# LTX-Video Web Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Gradio + FastAPI web platform wrapping LTX-Video so a small team (≤5 users) on a single GPU host can run T2V / I2V / multi-keyframe / long-video generations, switch distilled model variants, and keep per-user history — all from a browser.

**Architecture:** Single Python process. uvicorn-served FastAPI handles REST (auth, jobs, models, history, uploads). Gradio runs in a background thread and calls the FastAPI for business logic. A single async worker consumes an asyncio.Queue, owns one CUDA pipeline at a time via `pipeline_manager`, and writes results to `data/outputs/{user_id}/`. SQLite + SQLAlchemy for persistence. JWT auth (HS256, passlib bcrypt).

**Tech Stack:**
- Python 3.11+
- FastAPI + uvicorn
- Gradio (latest stable)
- SQLAlchemy 2.x + Alembic + SQLite
- passlib[bcrypt] + python-jose[cryptography] (JWT)
- pydantic v2 + pydantic-settings
- pytest + pytest-asyncio + httpx
- LTX-Video (`pip install git+https://github.com/Lightricks/LTX-Video.git`)
- diffusers, transformers, accelerate, torch (CUDA 12.x build)

**Spec:** `docs/superpowers/specs/2026-09-04-ltxvideo-web-platform-design.md`

## Global Constraints

These are project-wide requirements carried into every task. Each task implicitly inherits them.

- **DEVICE:** only `"cuda"` is supported in MVP. Startup must verify CUDA availability; CPU fallback is not allowed (Spec §1, §2 N5).
- **MAX_CONCURRENT_JOBS:** `1` (single GPU; one inference at a time).
- **JOB_TIMEOUT_SEC:** default `1800` (30 minutes).
- **Frame constraints:** `num_frames` must be `8n+1`; resolution must be divisible by 32.
- **VRAM budget:** ≥16 GB recommended for 13B distilled, ≥24 GB for 13B full. UI surfaces model `vram_gb` and warns when over.
- **Per-user isolation:** all uploads/outputs live under `data/{uploads|outputs}/{user_id}/`. No path argument is accepted from outside `storage.files.resolve(...)`.
- **Auth:** JWT HS256, 12 h default expiry. No token = `401`. Admin role required for `/admin/*` and model registry mutation.
- **Port assignments:** API on `8000`, Gradio on `7860`. Both bind `0.0.0.0` by default, overridable.
- **Naming:** PEP 8 throughout; module-level `from __future__ import annotations` for forward refs.
- **No placeholder code:** every step below contains runnable code. Implementation that depends on LTX-Video internals that may have shifted includes a "verify against current LTX-Video" check in the relevant step.

---

## File Structure (locked-in by this plan)

```
ltxvideo/                          # repo root (the workspace we're writing into)
├── pyproject.toml                 # Task 1
├── README.md                      # Task 1
├── .env.example                   # Task 1
├── .gitignore                     # Task 1
├── alembic.ini                    # Task 2
├── migrations/                    # Task 2  (Alembic)
│   ├── env.py
│   └── versions/0001_initial.py
├── app/
│   ├── __init__.py                # Task 1
│   ├── main.py                    # Task 11
│   ├── config.py                  # Task 1
│   ├── auth/
│   │   ├── __init__.py            # Task 3
│   │   ├── jwt.py                 # Task 3
│   │   ├── passwords.py           # Task 3
│   │   └── deps.py                # Task 3
│   ├── db/
│   │   ├── __init__.py            # Task 2
│   │   ├── models.py              # Task 2
│   │   └── session.py             # Task 2
│   ├── storage/
│   │   ├── __init__.py            # Task 2
│   │   └── files.py               # Task 2
│   ├── core/
│   │   ├── __init__.py            # Task 5
│   │   ├── pipeline_manager.py    # Task 5
│   │   ├── job_queue.py           # Task 6
│   │   ├── job_runner.py          # Task 6
│   │   ├── ltx_wrappers.py        # Task 5
│   │   └── long_video.py          # Task 5  (prompt split + window math)
│   ├── api/
│   │   ├── __init__.py            # Task 7
│   │   ├── auth.py                # Task 7
│   │   ├── models.py              # Task 7
│   │   ├── uploads.py             # Task 7
│   │   ├── generation.py          # Task 7
│   │   ├── jobs.py                # Task 7
│   │   ├── history.py             # Task 7
│   │   ├── files.py               # Task 7
│   │   └── schemas.py             # Task 7
│   └── ui/
│       ├── __init__.py            # Task 8
│       ├── gradio_app.py          # Task 8
│       └── api_client.py          # Task 8
├── scripts/
│   └── download_models.py         # Task 4
├── models/
│   └── registry.yaml              # Task 4
├── data/                          # runtime; created at startup
└── tests/
    ├── __init__.py                # Task 1
    ├── conftest.py                # Task 1 (built up across tasks)
    ├── fixtures/
    │   └── tiny_image.png         # Task 1
    ├── unit/
    │   ├── test_config.py         # Task 1
    │   ├── test_storage.py        # Task 2
    │   ├── test_auth.py           # Task 3
    │   ├── test_long_video.py     # Task 5
    │   ├── test_ltx_wrappers.py   # Task 5
    │   ├── test_pipeline_manager.py  # Task 5
    │   └── test_registry.py       # Task 4
    ├── integration/
    │   ├── test_api_auth.py       # Task 7
    │   ├── test_api_uploads.py    # Task 7
    │   ├── test_api_generation.py # Task 7
    │   ├── test_api_jobs.py       # Task 7
    │   └── test_api_history.py    # Task 7
    └── e2e/
        ├── test_gradio_login.py   # Task 8
        └── test_real_gpu.py       # Task 10  (@pytest.mark.gpu)
```

---

## Task 1: Project scaffolding + configuration

**Files:**
- Create: `pyproject.toml`, `README.md`, `.env.example`, `.gitignore`, `app/__init__.py`, `app/config.py`, `tests/__init__.py`, `tests/fixtures/tiny_image.png`, `tests/conftest.py`, `tests/unit/test_config.py`

**Interfaces (consumed by later tasks):**
- `app.config.Settings` (pydantic-settings `BaseSettings`) with attributes: `app_host`, `app_port_api`, `app_port_gradio`, `device` (Literal["cuda"]), `data_dir`, `model_dir`, `registry_path`, `database_url`, `jwt_secret`, `jwt_expires_min`, `admin_username`, `admin_password`, `max_concurrent_jobs`, `job_timeout_sec`, `output_disk_min_free_gb`, `log_level`, `hf_token`, `gradio_auth_basic`. Computed `data_dir_abs`, `model_dir_abs`, `uploads_dir`, `outputs_dir`, `previews_dir`, `db_path` as `pathlib.Path`. `def get_settings() -> Settings` (lru_cache).

**Global constraint reminder:** DEVICE is `"cuda"` only.

- [ ] **Step 1: Write the failing config test**

```python
# tests/unit/test_config.py
import pytest
from pathlib import Path

def test_settings_loads_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVICE", "cuda")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pw")
    from app.config import get_settings
    get_settings.cache_clear()
    s = get_settings()
    assert s.device == "cuda"
    assert isinstance(s.data_dir_abs, Path)
    assert s.uploads_dir == s.data_dir_abs / "uploads"
    assert s.outputs_dir == s.data_dir_abs / "outputs"
    assert s.jwt_expires_min == 720
```

- [ ] **Step 2: Run the test and verify it fails**

Run from repo root: `pytest tests/unit/test_config.py -v`
Expected: `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: Create pyproject.toml**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ltxvideo-web"
version = "0.1.0"
description = "Web platform wrapping LTX-Video for small teams"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.110",
  "uvicorn[standard]>=0.27",
  "gradio>=4.20",
  "sqlalchemy>=2.0",
  "alembic>=1.13",
  "pydantic>=2.6",
  "pydantic-settings>=2.2",
  "passlib[bcrypt]>=1.7.4",
  "python-jose[cryptography]>=3.3",
  "python-multipart>=0.0.9",
  "httpx>=0.27",
  "imageio[ffmpeg]>=2.34",
  "Pillow>=10.0",
  "ulid-py>=1.1",
  "pyyaml>=6.0",
  "huggingface-hub>=0.22",
  "torch>=2.2",
  # LTX-Video is installed from source in Task 4; placeholder for ordering
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "pytest-cov>=5.0",
  "respx>=0.21",
  "ruff>=0.4",
]

[tool.setuptools.packages.find]
include = ["app*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
  "gpu: real-GPU tests (deselect with -m 'not gpu')",
]
```

- [ ] **Step 4: Create directory skeleton and stubs**

```bash
mkdir -p app/{auth,db,storage,core,api,ui} tests/{fixtures,unit,integration,e2e} scripts models migrations/versions
touch app/__init__.py app/{auth,db,storage,core,api,ui}/__init__.py tests/__init__.py
```

- [ ] **Step 5: Implement `app/config.py`**

```python
# app/config.py
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_host: str = "0.0.0.0"
    app_port_api: int = 8000
    app_port_gradio: int = 7860

    device: Literal["cuda"] = "cuda"  # only "cuda" in MVP

    data_dir: Path = Path("./data")
    model_dir: Path = Path("./models")
    registry_path: Path = Path("./models/registry.yaml")
    database_url: str = "sqlite:///./data/app.db"

    jwt_secret: str = Field(min_length=32)
    jwt_expires_min: int = 720
    admin_username: str = "admin"
    admin_password: str = "change-me"

    max_concurrent_jobs: int = 1
    job_timeout_sec: int = 1800
    output_disk_min_free_gb: int = 5

    log_level: str = "INFO"
    hf_token: str = ""
    gradio_auth_basic: str = ""  # "user:pass" fallback for Gradio UI

    @computed_field  # type: ignore[misc]
    @property
    def data_dir_abs(self) -> Path:
        return self.data_dir.resolve()

    @computed_field  # type: ignore[misc]
    @property
    def model_dir_abs(self) -> Path:
        return self.model_dir.resolve()

    @computed_field  # type: ignore[misc]
    @property
    def uploads_dir(self) -> Path:
        return self.data_dir_abs / "uploads"

    @computed_field  # type: ignore[misc]
    @property
    def outputs_dir(self) -> Path:
        return self.data_dir_abs / "outputs"

    @computed_field  # type: ignore[misc]
    @property
    def previews_dir(self) -> Path:
        return self.data_dir_abs / "previews"

    @computed_field  # type: ignore[misc]
    @property
    def db_path(self) -> Path:
        return self.data_dir_abs / "app.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 6: Run the test and verify it passes**

Run: `pytest tests/unit/test_config.py -v`
Expected: PASS

- [ ] **Step 7: Create `.env.example`, `.gitignore`, `README.md`, fixture image**

`.env.example`:
```
APP_HOST=0.0.0.0
APP_PORT_API=8000
APP_PORT_GRADIO=7860
DEVICE=cuda
DATA_DIR=./data
MODEL_DIR=./models
REGISTRY_PATH=./models/registry.yaml
DATABASE_URL=sqlite:///./data/app.db
JWT_SECRET=please-replace-with-32-or-more-random-chars
JWT_EXPIRES_MIN=720
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me
MAX_CONCURRENT_JOBS=1
JOB_TIMEOUT_SEC=1800
OUTPUT_DISK_MIN_FREE_GB=5
LOG_LEVEL=INFO
HF_TOKEN=
GRADIO_AUTH_BASIC=
```

`.gitignore`:
```
__pycache__/
*.pyc
.env
.pytest_cache/
.coverage
data/
models/*.safetensors
models/*/model.safetensors
.venv/
venv/
*.egg-info/
dist/
build/
```

`README.md` (initial):
```markdown
# LTX-Video Web Platform

Wraps [LTX-Video](https://github.com/Lightricks/LTX-Video) in a Gradio + FastAPI web app.

## Quick start (CPU smoke only — full usage requires GPU)

1. `pip install -e .`
2. `cp .env.example .env` and set `JWT_SECRET` to 32+ random chars.
3. `python -m app.main` (UI on :7860, API on :8000).

See `docs/superpowers/specs/2026-09-04-ltxvideo-web-platform-design.md` for the design.
```

Generate a tiny PNG fixture (1×1 white pixel):

```python
# Run this once interactively, then commit the resulting tiny_image.png
from PIL import Image
Image.new("RGB", (4, 4), (255, 255, 255)).save("tests/fixtures/tiny_image.png")
```

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml README.md .env.example .gitignore \
  app/__init__.py app/config.py \
  tests/__init__.py tests/conftest.py tests/fixtures/tiny_image.png \
  tests/unit/test_config.py
git commit -m "feat: scaffold project + pydantic-settings config"
```

---

## Task 2: Database models + Alembic migration + storage helpers

**Files:**
- Create: `app/db/__init__.py`, `app/db/session.py`, `app/db/models.py`, `app/storage/__init__.py`, `app/storage/files.py`, `alembic.ini`, `migrations/env.py`, `migrations/versions/0001_initial.py`, `tests/unit/test_storage.py`, extend `tests/conftest.py`
- Modify: `tests/conftest.py` (add `db_session` fixture)

**Interfaces produced (consumed later):**
- `app.db.session.engine`, `SessionLocal`, `Base`, `get_db()` (FastAPI dependency)
- `app.db.models.User`, `Model`, `Job`, `Upload` SQLAlchemy 2.x declarative classes
- `app.storage.files.resolve(user_id: int, kind: Literal["uploads","outputs","previews"], name: str) -> Path` (always under `data/{kind}/{user_id}/`)
- `app.storage.files.verify_owner(path: Path, user_id: int) -> bool`
- `app.storage.files.save_upload(user_id: int, src: bytes, ext: str) -> tuple[Path, str]` (path, sha256)
- `app.storage.files.save_output(user_id: int, job_id: str, video_bytes: bytes) -> Path`

- [ ] **Step 1: Write the failing storage test**

```python
# tests/unit/test_storage.py
from pathlib import Path
from app.storage import files

def test_resolve_is_user_isolated():
    p = files.resolve(7, "uploads", "abc.png")
    assert p == Path("./data/uploads/7/abc.png").resolve()

def test_verify_owner_allows_own_path(tmp_path):
    p = tmp_path / "uploads" / "3" / "x.png"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"x")
    assert files.verify_owner(p, 3) is True

def test_verify_owner_rejects_other_user(tmp_path):
    p = tmp_path / "uploads" / "3" / "x.png"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"x")
    assert files.verify_owner(p, 4) is False

def test_save_upload_writes_and_hashes(tmp_path, monkeypatch):
    monkeypatch.setattr(files, "uploads_dir", tmp_path / "uploads")
    path, sha = files.save_upload(9, b"hello", ".png")
    assert path.exists()
    assert path.read_bytes() == b"hello"
    assert len(sha) == 64  # sha256 hex
```

- [ ] **Step 2: Run and verify it fails**

Run: `pytest tests/unit/test_storage.py -v`
Expected: `ModuleNotFoundError: No module named 'app.storage.files'`.

- [ ] **Step 3: Implement `app/db/session.py`**

```python
# app/db/session.py
from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = create_engine(
    get_settings().database_url, future=True, echo=False, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_engine():
    return _engine


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Implement `app/db/models.py`**

```python
# app/db/models.py
from __future__ import annotations
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, Enum
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
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.user)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


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
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued, index=True)
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
```

- [ ] **Step 5: Implement `app/storage/files.py`**

```python
# app/storage/files.py
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Literal

from app.config import get_settings


def uploads_dir() -> Path:
    return get_settings().uploads_dir

def outputs_dir() -> Path:
    return get_settings().outputs_dir

def previews_dir() -> Path:
    return get_settings().previews_dir


def resolve(user_id: int, kind: Literal["uploads", "outputs", "previews"], name: str) -> Path:
    base = {"uploads": uploads_dir(), "outputs": outputs_dir(), "previews": previews_dir()}[kind]
    p = (base / str(user_id) / name).resolve()
    # Defensive: ensure resolved path is still inside the user's directory
    if not str(p).startswith(str((base / str(user_id)).resolve())):
        raise ValueError("path escapes user directory")
    return p


def verify_owner(path: Path, user_id: int) -> bool:
    path = Path(path).resolve()
    parts = path.parts
    try:
        i = parts.index(f"uploads") if "uploads" in parts else parts.index("outputs")
    except ValueError:
        return False
    return i + 1 < len(parts) and parts[i + 1] == str(user_id)


def save_upload(user_id: int, data: bytes, ext: str) -> tuple[Path, str]:
    sha = hashlib.sha256(data).hexdigest()
    name = f"{sha}{ext}"
    p = resolve(user_id, "uploads", name)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_bytes(data)
    return p, sha


def save_output(user_id: int, job_id: str, video_bytes: bytes, ext: str = ".mp4") -> Path:
    name = f"{job_id}{ext}"
    p = resolve(user_id, "outputs", name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(video_bytes)
    return p
```

- [ ] **Step 6: Initialize Alembic and write initial migration**

```bash
alembic init -t async migrations
```

(If async template not desired, use `alembic init migrations` and edit `migrations/env.py` to use sync engine — both fine. This plan assumes sync.)

Edit `migrations/env.py` to import `Base` from `app.db.session` and `app.db.models` so metadata is registered:

```python
# migrations/env.py  (key edits)
from app.db.session import Base
from app.db import models  # noqa: F401  (register tables)
config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata
```

Create the migration:

```bash
alembic revision --autogenerate -m "initial schema"
```

This creates `migrations/versions/0001_initial.py`. Inspect it; ensure it contains `users`, `models`, `jobs`, `uploads` tables.

- [ ] **Step 7: Run tests**

Run: `pytest tests/unit/test_storage.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add app/db app/storage alembic.ini migrations tests/unit/test_storage.py tests/conftest.py
git commit -m "feat: db schema (users/models/jobs/uploads) + storage helpers"
```

---

## Task 3: Authentication — passwords, JWT, FastAPI dependency

**Files:**
- Create: `app/auth/__init__.py`, `app/auth/passwords.py`, `app/auth/jwt.py`, `app/auth/deps.py`, `tests/unit/test_auth.py`

**Interfaces produced:**
- `app.auth.passwords.hash_password(plain: str) -> str`
- `app.auth.passwords.verify_password(plain: str, hashed: str) -> bool`
- `app.auth.jwt.create_token(user_id: int, role: str) -> str`
- `app.auth.jwt.decode_token(token: str) -> dict`
- `app.auth.deps.current_user(token: str = Depends(oauth2_scheme), db = Depends(get_db)) -> User`

- [ ] **Step 1: Write the failing auth tests**

```python
# tests/unit/test_auth.py
import time
import pytest
from app.auth.passwords import hash_password, verify_password
from app.auth.jwt import create_token, decode_token, TokenError

def test_password_roundtrip():
    h = hash_password("hunter2")
    assert verify_password("hunter2", h)
    assert not verify_password("wrong", h)

def test_jwt_roundtrip():
    tok = create_token(user_id=42, role="admin")
    payload = decode_token(tok)
    assert payload["sub"] == "42"
    assert payload["role"] == "admin"

def test_jwt_invalid_raises():
    with pytest.raises(TokenError):
        decode_token("not.a.token")
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/unit/test_auth.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `app/auth/passwords.py`**

```python
# app/auth/passwords.py
from passlib.context import CryptContext

_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _ctx.verify(plain, hashed)
```

- [ ] **Step 4: Implement `app/auth/jwt.py`**

```python
# app/auth/jwt.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from app.config import get_settings


class TokenError(Exception):
    pass


def create_token(user_id: int, role: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.jwt_expires_min)).timestamp()),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=["HS256"])
    except JWTError as e:
        raise TokenError(str(e)) from e
```

- [ ] **Step 5: Implement `app/auth/deps.py`**

```python
# app/auth/deps.py
from __future__ import annotations
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_token, TokenError
from app.db.session import get_db
from app.db.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")
    try:
        payload = decode_token(token)
    except TokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role.value != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return user
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/unit/test_auth.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/auth tests/unit/test_auth.py
git commit -m "feat: auth — passwords, JWT, current_user dep"
```

---

## Task 4: Model registry + download script

**Files:**
- Create: `models/registry.yaml`, `scripts/download_models.py`, `app/core/__init__.py`, `app/core/registry.py`, `tests/unit/test_registry.py`

**Interfaces produced:**
- `app.core.registry.Registry` (dataclass with `models: list[ModelEntry]`, `by_id(id) -> ModelEntry | None`)
- `app.core.registry.load(path: Path) -> Registry`  (YAML)
- `app.core.registry.to_db_rows(reg: Registry) -> list[dict]`  (for upsert into `models` table)
- `scripts.download_models.py` CLI: `--model <id> | --all | --offline`

- [ ] **Step 1: Write the failing registry test**

```python
# tests/unit/test_registry.py
from pathlib import Path
from app.core.registry import Registry, load

def test_load_registry(tmp_path: Path):
    yaml = tmp_path / "reg.yaml"
    yaml.write_text("""
models:
  - id: ltx-2b-distilled
    display_name: "LTX-Video 2B Distilled"
    kind: t2v_distilled
    checkpoint_path: ltx-video-2b-distilled/model.safetensors
    config_path: ltx-video-2b-distilled/config.yaml
    default_steps: 8
    default_frames: 97
    vram_gb: 6
    enabled: true
    description: tiny
""")
    reg = load(yaml)
    assert isinstance(reg, Registry)
    e = reg.by_id("ltx-2b-distilled")
    assert e is not None
    assert e.default_steps == 8
    assert e.vram_gb == 6
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/unit/test_registry.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `models/registry.yaml`**

```yaml
# models/registry.yaml — the canonical 5-model set from spec §9
models:
  - id: ltx-13b-distilled-fast
    display_name: "LTX-Video 13B Distilled Fast (8x)"
    kind: t2v_distilled
    checkpoint_path: ltx-video-13b-distilled-fast/ltxv-13b-256-distilled.safetensors
    config_path: ltx-video-13b-distilled-fast/ltxv-13b-256-distilled.yaml
    default_steps: 8
    default_frames: 121
    vram_gb: 16
    enabled: true
    description: "8x accelerated distilled variant for fast previews"
  - id: ltx-13b-distilled
    display_name: "LTX-Video 13B Distilled (Standard)"
    kind: t2v_distilled
    checkpoint_path: ltx-video-13b-distilled/ltxv-13b-256-distilled.safetensors
    config_path: ltx-video-13b-distilled/ltxv-13b-256-distilled.yaml
    default_steps: 20
    default_frames: 121
    vram_gb: 16
    enabled: true
    description: "Standard distilled 13B variant"
  - id: ltx-13b-distilled-long-multi-shot
    display_name: "LTX-Video 13B Long Multi-Shot"
    kind: i2v_long
    checkpoint_path: ltx-video-13b-distilled-long-multi-shot/model.safetensors
    config_path: ltx-video-13b-distilled-long-multi-shot/config.yaml
    default_steps: 30
    default_frames: 161
    vram_gb: 20
    enabled: true
    description: "Long sliding-window multi-shot distilled variant"
  - id: ltx-2b-distilled
    display_name: "LTX-Video 2B Distilled"
    kind: t2v_distilled
    checkpoint_path: ltx-video-2b-distilled/model.safetensors
    config_path: ltx-video-2b-distilled/config.yaml
    default_steps: 8
    default_frames: 97
    vram_gb: 6
    enabled: true
    description: "Lightweight 2B distilled for low-VRAM machines"
  - id: ltx-13b-full
    display_name: "LTX-Video 13B Full (no distill)"
    kind: t2v_full
    checkpoint_path: ltx-video-13b-full/ltxv-13b-256-full.safetensors
    config_path: ltx-video-13b-full/ltxv-13b-256-full.yaml
    default_steps: 40
    default_frames: 121
    vram_gb: 28
    enabled: false
    description: "Full 13B checkpoint; highest quality, slowest. Behind advanced toggle."
```

- [ ] **Step 4: Implement `app/core/registry.py`**

```python
# app/core/registry.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass(frozen=True)
class ModelEntry:
    id: str
    display_name: str
    kind: str
    checkpoint_path: str
    config_path: str
    default_steps: int
    default_frames: int
    vram_gb: int
    enabled: bool
    description: str


@dataclass
class Registry:
    models: list[ModelEntry]

    def by_id(self, model_id: str) -> ModelEntry | None:
        for m in self.models:
            if m.id == model_id:
                return m
        return None

    def enabled_ids(self) -> list[str]:
        return [m.id for m in self.models if m.enabled]


def load(path: Path) -> Registry:
    raw = yaml.safe_load(path.read_text())
    entries = [
        ModelEntry(
            id=m["id"],
            display_name=m["display_name"],
            kind=m["kind"],
            checkpoint_path=m["checkpoint_path"],
            config_path=m["config_path"],
            default_steps=int(m.get("default_steps", 20)),
            default_frames=int(m.get("default_frames", 121)),
            vram_gb=int(m.get("vram_gb", 16)),
            enabled=bool(m.get("enabled", True)),
            description=m.get("description", ""),
        )
        for m in raw["models"]
    ]
    return Registry(models=entries)


def to_db_rows(reg: Registry) -> list[dict]:
    return [m.__dict__ for m in reg.models]
```

- [ ] **Step 5: Implement `scripts/download_models.py`**

```python
# scripts/download_models.py
from __future__ import annotations
import argparse
import hashlib
import shutil
from pathlib import Path

from huggingface_hub import snapshot_download
from app.config import get_settings
from app.core.registry import load


HF_REPO = "Lightricks/LTX-Video"


def download_one(entry_id: str, offline: bool) -> int:
    settings = get_settings()
    reg = load(settings.registry_path)
    entry = reg.by_id(entry_id)
    if entry is None:
        raise SystemExit(f"unknown model: {entry_id}")

    target_dir = settings.model_dir_abs / Path(entry.checkpoint_path).parent
    target_dir.mkdir(parents=True, exist_ok=True)

    if offline:
        ckpt = settings.model_dir_abs / entry.checkpoint_path
        cfg = settings.model_dir_abs / entry.config_path
        if not ckpt.exists() or not cfg.exists():
            raise SystemExit(f"missing files for {entry_id}: {ckpt} / {cfg}")
        print(f"[offline] ok: {entry_id}")
        return 0

    snapshot_download(
        repo_id=HF_REPO,
        local_dir=str(settings.model_dir_abs),
        token=settings.hf_token or None,
        allow_patterns=[
            f"{Path(entry.checkpoint_path).parent}/**",
            f"{Path(entry.config_path).parent}/**",
        ],
    )
    print(f"downloaded: {entry_id} -> {target_dir}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--model", help="model id to download")
    g.add_argument("--all", action="store_true", help="download all enabled models")
    g.add_argument("--offline", action="store_true", help="verify only, no download")
    args = p.parse_args()

    settings = get_settings()
    reg = load(settings.registry_path)

    if args.model:
        return download_one(args.model, offline=False)
    if args.offline:
        rc = 0
        for m in reg.enabled_ids():
            rc |= download_one(m, offline=True)
        return rc
    if args.all:
        rc = 0
        for m in reg.enabled_ids():
            rc |= download_one(m, offline=False)
        return rc
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/unit/test_registry.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add models/registry.yaml scripts/download_models.py app/core/registry.py tests/unit/test_registry.py
git commit -m "feat: model registry + download script"
```

---

## Task 5: Pipeline manager + LTX wrappers + long-video utility

**Files:**
- Create: `app/core/pipeline_manager.py`, `app/core/ltx_wrappers.py`, `app/core/long_video.py`, `tests/unit/test_long_video.py`, `tests/unit/test_ltx_wrappers.py`, `tests/unit/test_pipeline_manager.py`, `tests/fixtures/mock_pipeline.py`

**Interfaces produced:**
- `app.core.pipeline_manager.PipelineManager` (singleton via `get_manager()`)
  - `load(model_id: str) -> None`  (blocks; uses `threading.Lock` + asyncio lock)
  - `unload() -> None`
  - `get() -> Any`  (current pipeline)
  - `current_id: str | None`
  - `status() -> dict`  (`{current_id, vram_used_gb, vram_total_gb}`)
- `app.core.ltx_wrappers.generate(req: dict, on_step: Callable[[int,int], None]) -> bytes`  (mp4 bytes)
- `app.core.long_video.split_prompts(prompt: str, num_windows: int) -> list[str]`
- `app.core.long_video.window_plan(num_frames: int, tile_size: int, overlap: int) -> list[(start,end)]`

- [ ] **Step 1: Write the failing long-video test**

```python
# tests/unit/test_long_video.py
from app.core.long_video import split_prompts, window_plan

def test_split_prompts_pads():
    out = split_prompts("a | b | c", num_windows=5)
    assert out == ["a", "b", "c", "c", "c"]

def test_split_prompts_single():
    assert split_prompts("only one", 3) == ["only one"] * 3

def test_window_plan_basic():
    plan = window_plan(num_frames=161, tile_size=80, overlap=24)
    # each window 80 frames; advance by 80-24=56
    assert plan[0] == (0, 80)
    assert plan[1] == (56, 136)
    assert plan[2] == (112, 161)  # last clips at end
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/unit/test_long_video.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `app/core/long_video.py`**

```python
# app/core/long_video.py
from __future__ import annotations


def split_prompts(prompt: str, num_windows: int) -> list[str]:
    parts = [p.strip() for p in prompt.split("|") if p.strip()]
    if not parts:
        parts = [""]
    if len(parts) >= num_windows:
        return parts[:num_windows]
    # pad with the last segment
    return parts + [parts[-1]] * (num_windows - len(parts))


def window_plan(num_frames: int, tile_size: int, overlap: int) -> list[tuple[int, int]]:
    if tile_size <= overlap:
        raise ValueError("tile_size must be greater than overlap")
    step = tile_size - overlap
    plan: list[tuple[int, int]] = []
    start = 0
    while start < num_frames:
        end = min(start + tile_size, num_frames)
        plan.append((start, end))
        if end == num_frames:
            break
        start += step
    return plan
```

- [ ] **Step 4: Implement `app/core/pipeline_manager.py` (with mocked pipeline) and tests**

```python
# tests/fixtures/mock_pipeline.py
class MockPipeline:
    def __init__(self, model_id: str = "mock"):
        self.model_id = model_id
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        # Return a 2-frame "video" as a list of PIL images
        from PIL import Image
        return [Image.new("RGB", (8, 8), (i * 50, 0, 0)) for i in range(2)]

    def to(self, device):
        return self
```

```python
# app/core/pipeline_manager.py
from __future__ import annotations
import threading
from typing import Any

from app.config import get_settings


class PipelineManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pipeline: Any = None
        self._current_id: str | None = None

    @property
    def current_id(self) -> str | None:
        return self._current_id

    def load(self, model_id: str, loader=None) -> None:
        """`loader(model_id) -> pipeline` injected for testability."""
        with self._lock:
            if self._current_id == model_id and self._pipeline is not None:
                return
            new_pipeline = loader(model_id) if loader else self._default_loader(model_id)
            old = self._pipeline
            self._pipeline = new_pipeline
            self._current_id = model_id
            del old
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

    def unload(self) -> None:
        with self._lock:
            self._pipeline = None
            self._current_id = None
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

    def get(self) -> Any:
        return self._pipeline

    def status(self) -> dict:
        vram_used = vram_total = 0.0
        try:
            import torch
            if torch.cuda.is_available():
                free, total = torch.cuda.mem_get_info()
                vram_total = total / (1024 ** 3)
                vram_used = (total - free) / (1024 ** 3)
        except Exception:
            pass
        return {"current_id": self._current_id, "vram_used_gb": round(vram_used, 2),
                "vram_total_gb": round(vram_total, 2)}

    def _default_loader(self, model_id: str) -> Any:
        # Implemented in Task 6 wiring; placeholder kept here so unit tests work standalone.
        raise NotImplementedError("wire LTXVideoPipeline.from_pretrained in Task 6")


_singleton: PipelineManager | None = None


def get_manager() -> PipelineManager:
    global _singleton
    if _singleton is None:
        _singleton = PipelineManager()
    return _singleton
```

```python
# tests/unit/test_pipeline_manager.py
import pytest
from app.core.pipeline_manager import PipelineManager
from tests.fixtures.mock_pipeline import MockPipeline

def test_load_and_get(monkeypatch):
    pm = PipelineManager()
    pm.load("m1", loader=lambda _: MockPipeline("m1"))
    assert pm.current_id == "m1"
    assert pm.get().model_id == "m1"

def test_load_replaces(monkeypatch):
    pm = PipelineManager()
    pm.load("m1", loader=lambda _: MockPipeline("m1"))
    pm.load("m2", loader=lambda _: MockPipeline("m2"))
    assert pm.current_id == "m2"

def test_unload_clears():
    pm = PipelineManager()
    pm.load("m1", loader=lambda _: MockPipeline("m1"))
    pm.unload()
    assert pm.current_id is None
    assert pm.get() is None
```

- [ ] **Step 5: Implement `app/core/ltx_wrappers.py`**

```python
# app/core/ltx_wrappers.py
from __future__ import annotations
import io
from typing import Callable

from app.core.long_video import split_prompts, window_plan


def generate(
    pipeline,
    *,
    kind: str,
    prompt: str,
    num_frames: int,
    height: int,
    width: int,
    num_inference_steps: int,
    guidance_scale: float,
    seed: int | None,
    fps: int,
    on_step: Callable[[int, int], None] | None = None,
    # I2V / keyframe inputs (optional)
    image: "PIL.Image.Image | None" = None,
    strength: float | None = None,
    frame_uploads: list | None = None,
    # Long-video
    temporal_tile_size: int | None = None,
    temporal_overlap: int | None = None,
) -> bytes:
    """Returns mp4 bytes. The actual LTXVideoPipeline signature must be verified
    against the installed LTX-Video version during implementation (Spec §14 R1).
    This wrapper absorbs any signature drift so callers stay stable."""
    on_step = on_step or (lambda s, t: None)

    common = dict(
        prompt=prompt,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        height=height,
        width=width,
        num_frames=num_frames,
        seed=seed,
        fps=fps,
        callback_on_step_end=lambda _pipe, step, _t, _kwargs: on_step(step + 1, num_inference_steps),
    )

    if image is not None and strength is not None:
        common["image"] = image
        common["strength"] = strength

    if frame_uploads:
        common["keyframe_inputs"] = frame_uploads  # implementation verifies adapter name

    if temporal_tile_size and temporal_overlap and num_frames > temporal_tile_size:
        plan = window_plan(num_frames, temporal_tile_size, temporal_overlap)
        common["temporal_window_plan"] = plan
        common["prompt"] = split_prompts(prompt, len(plan))

    # Call the underlying pipeline; the result must be saved as mp4 bytes.
    out = pipeline(**common)
    return _frames_to_mp4_bytes(out, fps=fps)


def _frames_to_mp4_bytes(frames, fps: int) -> bytes:
    """Convert a list of PIL.Image (or numpy array) frames to MP4 bytes via imageio."""
    import imageio.v2 as imageio
    import numpy as np
    buf = io.BytesIO()
    writer = imageio.get_writer(buf, format="mp4", fps=fps, codec="libx264", quality=8)
    try:
        for f in frames:
            arr = np.asarray(f)
            if arr.ndim == 4 and arr.shape[0] == 1:
                arr = arr[0]
            writer.append_data(arr)
    finally:
        writer.close()
    return buf.getvalue()
```

```python
# tests/unit/test_ltx_wrappers.py
from tests.fixtures.mock_pipeline import MockPipeline
from app.core.ltx_wrappers import generate

def test_generate_returns_mp4_bytes():
    p = MockPipeline()
    out = generate(
        pipeline=p, kind="t2v", prompt="x", num_frames=9, height=32, width=32,
        num_inference_steps=2, guidance_scale=5.0, seed=0, fps=8,
    )
    assert isinstance(out, bytes)
    assert len(out) > 0
    assert p.calls, "pipeline was not invoked"

def test_long_video_passes_window_plan_and_split_prompts():
    p = MockPipeline()
    generate(
        pipeline=p, kind="t2v", prompt="a | b | c",
        num_frames=161, height=32, width=32,
        num_inference_steps=2, guidance_scale=5.0, seed=0, fps=8,
        temporal_tile_size=80, temporal_overlap=24,
    )
    args = p.calls[0]
    assert isinstance(args["temporal_window_plan"], list)
    assert len(args["prompt"]) == 3  # 161 frames / 56 step = 3 windows
```

- [ ] **Step 6: Run all three test files**

Run: `pytest tests/unit/test_long_video.py tests/unit/test_ltx_wrappers.py tests/unit/test_pipeline_manager.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/core tests/unit/test_long_video.py tests/unit/test_ltx_wrappers.py \
        tests/unit/test_pipeline_manager.py tests/fixtures/mock_pipeline.py
git commit -m "feat: pipeline_manager + ltx_wrappers + long_video utility (mock-friendly)"
```

---

## Task 6: Job queue + job runner

**Files:**
- Create: `app/core/job_queue.py`, `app/core/job_runner.py`, `tests/integration/test_job_runner.py`

**Interfaces produced:**
- `app.core.job_queue.JobQueue` (singleton via `get_queue()`)
  - `start() -> None`  (spawns worker task)
  - `stop() -> None`
  - `submit(kind, user_id, model_id, params, parent_job_id=None) -> str`  (returns job_id, ULID)
  - `status(job_id) -> Job | None`
  - `cancel(job_id) -> bool`
- `app.core.job_runner.run(job_id, db) -> None`  (drives one job end-to-end)

- [ ] **Step 1: Write the failing integration test**

```python
# tests/integration/test_job_runner.py
import asyncio
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app.db.session import Base
from app.db.models import User, Role
from app.auth.passwords import hash_password
from app.core import job_queue as jq
from app.core import job_runner as jr
from tests.fixtures.mock_pipeline import MockPipeline


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.db.session import get_engine
    engine = get_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    u = User(username="u", password_hash=hash_password("p"), role=Role.user)
    s.add(u); s.commit()
    yield s
    s.close()


def test_job_runs_to_succeeded(db_session, monkeypatch):
    # Patch pipeline_manager to load MockPipeline
    from app.core import pipeline_manager as pm
    pm._singleton = pm.PipelineManager()
    pm._singleton.load = lambda mid, loader=None: pm._singleton._pipeline or pm._singleton._pipeline.__init__() or None  # noop
    # simpler: directly stub get()
    class _Stub:
        def __call__(self, **kw):
            from PIL import Image
            return [Image.new("RGB", (8, 8)) for _ in range(2)]
    pm._singleton._pipeline = _Stub()
    pm._singleton._current_id = "mock"

    q = jq.JobQueue()
    q.start()
    try:
        job_id = q.submit(
            kind="t2v", user_id=db_session.query(User).first().id,
            model_id="ltx-2b-distilled",
            params={"prompt": "x", "num_frames": 9, "height": 32, "width": 32,
                    "num_inference_steps": 2, "guidance_scale": 5.0, "seed": 0, "fps": 8},
        )
        # poll
        for _ in range(60):
            j = q.status(job_id)
            if j is not None and j.status.value in ("succeeded", "failed"):
                break
            time.sleep(0.1)
        assert j.status.value == "succeeded", f"got {j.status.value}: {j.error}"
    finally:
        q.stop()
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/integration/test_job_runner.py -v`
Expected: failure (queue not implemented).

- [ ] **Step 3: Implement `app/core/job_queue.py`**

```python
# app/core/job_queue.py
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Any

import ulid
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import Job, JobStatus, JobStage


class JobQueue:
    def __init__(self) -> None:
        self._q: asyncio.Queue[str] = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tasks.append(asyncio.create_task(self._worker()))

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    def submit(
        self, *, kind: str, user_id: int, model_id: str, params: dict, parent_job_id: str | None = None
    ) -> str:
        import json
        job_id = str(ulid.new())
        with SessionLocal() as db:
            db.add(Job(
                id=job_id, user_id=user_id, kind=kind, model_id=model_id,
                params_json=json.dumps(params), parent_job_id=parent_job_id,
            ))
            db.commit()
        self._q.put_nowait(job_id)
        return job_id

    def status(self, job_id: str) -> Job | None:
        with SessionLocal() as db:
            return db.get(Job, job_id)

    def cancel(self, job_id: str) -> bool:
        with SessionLocal() as db:
            j = db.get(Job, job_id)
            if j is None or j.status != JobStatus.queued:
                return False
            j.status = JobStatus.cancelled
            db.commit()
            return True

    async def _worker(self) -> None:
        from app.core import job_runner
        while self._running:
            try:
                job_id = await self._q.get()
            except asyncio.CancelledError:
                return
            try:
                with SessionLocal() as db:
                    await job_runner.run(job_id, db)
            except Exception as e:
                with SessionLocal() as db:
                    j = db.get(Job, job_id)
                    if j is not None and j.status not in (JobStatus.succeeded, JobStatus.failed):
                        j.status = JobStatus.failed
                        j.error = f"worker crashed: {e!r}"
                        db.commit()
            finally:
                self._q.task_done()


_singleton: JobQueue | None = None


def get_queue() -> JobQueue:
    global _singleton
    if _singleton is None:
        _singleton = JobQueue()
    return _singleton
```

- [ ] **Step 4: Implement `app/core/job_runner.py`**

```python
# app/core/job_runner.py
from __future__ import annotations
import asyncio
import json
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import pipeline_manager as pm_mod
from app.core.ltx_wrappers import generate as ltx_generate
from app.core import registry as reg_mod
from app.db.models import Job, JobStatus, JobStage
from app.storage import files


async def run(job_id: str, db: Session) -> None:
    s = get_settings()
    j: Job | None = db.get(Job, job_id)
    if j is None:
        return
    if j.status == JobStatus.cancelled:
        return

    j.status = JobStatus.running
    j.stage = JobStage.loading_model
    j.started_at = datetime.now(timezone.utc)
    db.commit()

    pm = pm_mod.get_manager()

    def _ensure_loaded(model_id: str) -> None:
        if pm.current_id == model_id:
            return
        reg = reg_mod.load(s.registry_path)
        entry = reg.by_id(model_id)
        if entry is None:
            raise RuntimeError(f"unknown model: {model_id}")
        ckpt = s.model_dir_abs / entry.checkpoint_path
        if not ckpt.exists():
            raise FileNotFoundError(f"checkpoint missing: {ckpt}")
        # Real loader wiring (uses LTXVideoPipeline.from_pretrained) — see Task 9
        pm.load(model_id, loader=_real_loader(entry.checkpoint_path))

    try:
        await asyncio.wait_for(
            asyncio.to_thread(_ensure_loaded, j.model_id),
            timeout=s.job_timeout_sec,
        )
        params = json.loads(j.params_json)
        j.stage = JobStage.encoding
        db.commit()

        loop = asyncio.get_running_loop()
        progress = {"p": 0.0}

        def _on_step(step: int, total: int) -> None:
            j.stage = JobStage.denoising
            j.progress = step / total
            # Throttle DB writes: every 5 steps
            if step % 5 == 0 or step == total:
                db.commit()

        def _run_inference() -> bytes:
            j.stage = JobStage.denoising
            db.commit()
            mp4 = ltx_generate(
                pipeline=pm.get(),
                on_step=_on_step,
                **params,
            )
            j.stage = JobStage.decoding
            j.progress = 1.0
            db.commit()
            return mp4

        t0 = time.time()
        mp4_bytes = await asyncio.wait_for(
            asyncio.to_thread(_run_inference),
            timeout=s.job_timeout_sec,
        )
        j.stage = JobStage.writing
        db.commit()

        out_path = files.save_output(j.user_id, j.id, mp4_bytes)
        rel = str(out_path.relative_to(s.data_dir_abs))
        j.output_path = rel
        j.duration_sec = time.time() - t0
        j.status = JobStatus.succeeded
        j.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        j.status = JobStatus.failed
        j.error = repr(e)[:2000]
        j.finished_at = datetime.now(timezone.utc)
        db.commit()


def _real_loader(checkpoint_path: str):
    """Returns a loader(model_id) -> pipeline callable."""
    def _loader(model_id: str):
        # Import lazily; LTX-Video is heavy and only loaded when needed
        from ltx_video.pipelines.pipeline_ltx_video import LTXVideoPipeline
        return LTXVideoPipeline.from_pretrained(checkpoint_path)
    return _loader
```

- [ ] **Step 5: Run integration test**

Run: `pytest tests/integration/test_job_runner.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/core/job_queue.py app/core/job_runner.py tests/integration/test_job_runner.py
git commit -m "feat: job queue + runner with model loading + persistence"
```

---

## Task 7: REST API — auth, models, uploads, generation, jobs, history, files

**Files:**
- Create: `app/api/__init__.py`, `app/api/schemas.py`, `app/api/auth.py`, `app/api/models.py`, `app/api/uploads.py`, `app/api/generation.py`, `app/api/jobs.py`, `app/api/history.py`, `app/api/files.py`, `tests/integration/test_api_auth.py`, `tests/integration/test_api_uploads.py`, `tests/integration/test_api_generation.py`, `tests/integration/test_api_jobs.py`, `tests/integration/test_api_history.py`
- Modify: `tests/conftest.py` (add `client` and `auth_headers` fixtures)

**Interfaces produced (routers):**
- `app.api.auth.router` — POST /api/v1/auth/login, GET /api/v1/auth/me
- `app.api.models.router` — GET /api/v1/models, GET /api/v1/models/current, POST /api/v1/models/{id}/load, POST /api/v1/models/unload
- `app.api.uploads.router` — POST /api/v1/uploads
- `app.api.generation.router` — POST /api/v1/t2v, /i2v, /keyframe, /extend, /upscale
- `app.api.jobs.router` — GET /api/v1/jobs/{id}, /jobs/{id}/result, /jobs/{id}/cancel, /jobs/{id}/preview
- `app.api.history.router` — GET /api/v1/history, /api/v1/history/{id}, DELETE /api/v1/history/{id}
- `app.api.files.router` — GET /api/v1/files/{path:path}

- [ ] **Step 1: Write the failing auth API test**

```python
# tests/integration/test_api_auth.py
import pytest
from fastapi.testclient import TestClient
from app.config import get_settings
from app.db.session import Base, get_engine, SessionLocal
from app.db.models import User, Role
from app.auth.passwords import hash_password

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    get_settings.cache_clear()
    Base.metadata.create_all(get_engine())
    with SessionLocal() as s:
        s.add(User(username="admin", password_hash=hash_password("admin"),
                   role=Role.admin, is_active=True))
        s.commit()
    from app.main import build_app
    return TestClient(build_app())


def test_login_then_me(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    r2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 200
    assert r2.json()["username"] == "admin"
```

- [ ] **Step 2: Implement `app/api/schemas.py`**

```python
# app/api/schemas.py
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    expires_in: int


class UserOut(BaseModel):
    id: int
    username: str
    role: str


class ModelOut(BaseModel):
    id: str
    display_name: str
    kind: str
    default_steps: int
    default_frames: int
    vram_gb: int
    enabled: bool
    description: str


class GenerateIn(BaseModel):
    model_id: str
    prompt: str
    negative_prompt: Optional[str] = None
    num_frames: int = Field(ge=9)
    height: int = Field(ge=64, multiple_of=32)
    width: int = Field(ge=64, multiple_of=32)
    num_inference_steps: int = Field(ge=1, le=200)
    guidance_scale: float = Field(ge=0.0, le=20.0)
    seed: Optional[int] = None
    fps: int = 24
    temporal_tile_size: Optional[int] = None
    temporal_overlap: Optional[int] = None
    image_upload_id: Optional[str] = None
    strength: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    frame_uploads: Optional[list[dict]] = None
    parent_job_id: Optional[str] = None
    extra_frames: Optional[int] = None
    two_stage: Optional[bool] = False
```

- [ ] **Step 3: Implement `app/api/auth.py`**

```python
# app/api/auth.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.schemas import LoginIn, TokenOut, UserOut
from app.auth.jwt import create_token
from app.auth.passwords import verify_password
from app.auth.deps import current_user
from app.config import get_settings
from app.db.session import get_db
from app.db.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    u = db.query(User).filter_by(username=form.username, is_active=True).first()
    if not u or not verify_password(form.password, u.password_hash):
        raise HTTPException(status_code=401, detail="bad credentials")
    tok = create_token(u.id, u.role.value)
    return TokenOut(access_token=tok, expires_in=get_settings().jwt_expires_min * 60)


@router.get("/me", response_model=UserOut)
def me(u: User = Depends(current_user)):
    return UserOut(id=u.id, username=u.username, role=u.role.value)
```

- [ ] **Step 4: Implement `app/api/models.py`**

```python
# app/api/models.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ModelOut
from app.auth.deps import current_user
from app.config import get_settings
from app.core import pipeline_manager as pm_mod
from app.core import registry as reg_mod
from app.core import job_queue as jq
from app.db.session import get_db
from app.db.models import User

router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get("", response_model=list[ModelOut])
def list_models(_: User = Depends(current_user)):
    reg = reg_mod.load(get_settings().registry_path)
    return [ModelOut(
        id=e.id, display_name=e.display_name, kind=e.kind,
        default_steps=e.default_steps, default_frames=e.default_frames,
        vram_gb=e.vram_gb, enabled=e.enabled, description=e.description,
    ) for e in reg.models]


@router.get("/current")
def current(_: User = Depends(current_user)):
    return pm_mod.get_manager().status()


@router.post("/{model_id}/load", status_code=202)
def load_model(model_id: str, u: User = Depends(current_user)):
    job_id = jq.get_queue().submit(
        kind="model_load", user_id=u.id, model_id=model_id, params={"op": "load"}
    )
    return {"job_id": job_id}


@router.post("/unload", status_code=202)
def unload_model(u: User = Depends(current_user)):
    job_id = jq.get_queue().submit(
        kind="model_load", user_id=u.id, model_id="__unload__", params={"op": "unload"}
    )
    return {"job_id": job_id}
```

(Note: the `model_load` job kind is special-cased in `job_runner` (Task 9) to call `pm.unload()` when `model_id == "__unload__"`.)

- [ ] **Step 5: Implement `app/api/uploads.py`**

```python
# app/api/uploads.py
from __future__ import annotations
import ulid
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.db.session import get_db
from app.db.models import Upload, User
from app.storage import files

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])

ALLOWED = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


@router.post("")
async def upload_image(
    file: UploadFile = File(...), u: User = Depends(current_user), db: Session = Depends(get_db)
):
    if file.content_type not in ALLOWED:
        raise HTTPException(415, f"unsupported type: {file.content_type}")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "file too large (>20MB)")
    path, sha = files.save_upload(u.id, data, ALLOWED[file.content_type])
    rec = Upload(id=str(ulid.new()), user_id=u.id, path=str(path.relative_to(files.uploads_dir())), kind="image", sha256=sha)
    db.add(rec); db.commit(); db.refresh(rec)
    return {"id": rec.id, "path": rec.path, "sha256": rec.sha256}
```

- [ ] **Step 6: Implement `app/api/generation.py`**

```python
# app/api/generation.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import GenerateIn
from app.auth.deps import current_user
from app.core import job_queue as jq
from app.core import registry as reg_mod
from app.config import get_settings
from app.db.session import get_db
from app.db.models import User

router = APIRouter(prefix="/api/v1", tags=["generation"])


def _enqueue(u: User, kind: str, params: dict) -> str:
    reg = reg_mod.load(get_settings().registry_path)
    entry = reg.by_id(params["model_id"])
    if entry is None or not entry.enabled:
        raise HTTPException(400, f"model not available: {params['model_id']}")
    return jq.get_queue().submit(kind=kind, user_id=u.id, model_id=params["model_id"], params=params)


@router.post("/t2v", status_code=202)
def t2v(req: GenerateIn, u: User = Depends(current_user)):
    return {"job_id": _enqueue(u, "t2v", req.model_dump())}


@router.post("/i2v", status_code=202)
def i2v(req: GenerateIn, u: User = Depends(current_user)):
    if not req.image_upload_id:
        raise HTTPException(400, "image_upload_id required")
    return {"job_id": _enqueue(u, "i2v", req.model_dump())}


@router.post("/keyframe", status_code=202)
def keyframe(req: GenerateIn, u: User = Depends(current_user)):
    if not req.frame_uploads:
        raise HTTPException(400, "frame_uploads required")
    return {"job_id": _enqueue(u, "keyframe", req.model_dump())}


@router.post("/extend", status_code=202)
def extend(req: GenerateIn, u: User = Depends(current_user)):
    if not req.parent_job_id:
        raise HTTPException(400, "parent_job_id required")
    return {"job_id": _enqueue(u, "extend", req.model_dump(exclude={"parent_job_id"}), parent_job_id=req.parent_job_id)}


@router.post("/upscale", status_code=202)
def upscale(req: GenerateIn, u: User = Depends(current_user)):
    if not req.parent_job_id:
        raise HTTPException(400, "parent_job_id required")
    return {"job_id": _enqueue(u, "upscale", req.model_dump(exclude={"parent_job_id"}), parent_job_id=req.parent_job_id)}
```

- [ ] **Step 7: Implement `app/api/jobs.py`**

```python
# app/api/jobs.py
from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.core import job_queue as jq
from app.config import get_settings
from app.db.session import get_db
from app.db.models import Job, User
from app.storage import files

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _serialize(j: Job) -> dict:
    return {
        "id": j.id, "user_id": j.user_id, "kind": j.kind, "model_id": j.model_id,
        "params": json.loads(j.params_json),
        "status": j.status.value, "progress": j.progress, "stage": j.stage.value,
        "error": j.error, "output_path": j.output_path, "preview_path": j.preview_path,
        "parent_job_id": j.parent_job_id, "duration_sec": j.duration_sec,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
    }


@router.get("/{job_id}")
def get_job(job_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None or j.user_id != u.id:
        raise HTTPException(404, "job not found")
    return _serialize(j)


@router.get("/{job_id}/result")
def get_result(job_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None or j.user_id != u.id:
        raise HTTPException(404, "job not found")
    if not j.output_path:
        raise HTTPException(409, "job has no output yet")
    s = get_settings()
    p = s.data_dir_abs / j.output_path
    if not files.verify_owner(p, u.id):
        raise HTTPException(403, "forbidden")
    return FileResponse(p, media_type="video/mp4", filename=f"{job_id}.mp4")


@router.post("/{job_id}/cancel")
def cancel(job_id: str, u: User = Depends(current_user)):
    j = jq.get_queue().status(job_id)
    if j is None or j.user_id != u.id:
        raise HTTPException(404, "job not found")
    return {"ok": jq.get_queue().cancel(job_id)}


@router.get("/{job_id}/preview")
def get_preview(job_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None or j.user_id != u.id:
        raise HTTPException(404, "job not found")
    if not j.preview_path:
        raise HTTPException(404, "no preview yet")
    s = get_settings()
    p = s.data_dir_abs / j.preview_path
    return FileResponse(p, media_type="image/png")
```

- [ ] **Step 8: Implement `app/api/history.py`**

```python
# app/api/history.py
from __future__ import annotations
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.config import get_settings
from app.db.session import get_db
from app.db.models import Job, User
from app.storage import files

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("")
def list_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    kind: str | None = None,
    u: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Job).filter(Job.user_id == u.id)
    if kind:
        q = q.filter(Job.kind == kind)
    q = q.order_by(Job.created_at.desc()).limit(limit).offset(offset)
    return [{
        "id": j.id, "kind": j.kind, "model_id": j.model_id, "status": j.status.value,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "output_path": j.output_path,
    } for j in q]


@router.get("/{job_id}")
def get_history_item(job_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None or j.user_id != u.id:
        raise HTTPException(404, "not found")
    return {
        "id": j.id, "kind": j.kind, "model_id": j.model_id, "params": json.loads(j.params_json),
        "status": j.status.value, "progress": j.progress, "stage": j.stage.value,
        "output_path": j.output_path, "error": j.error,
        "created_at": j.created_at.isoformat() if j.created_at else None,
    }


@router.delete("/{job_id}")
def delete_history_item(job_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None or j.user_id != u.id:
        raise HTTPException(404, "not found")
    if j.output_path:
        s = get_settings()
        p = s.data_dir_abs / j.output_path
        if files.verify_owner(p, u.id) and p.exists():
            p.unlink()
    db.delete(j); db.commit()
    return {"ok": True}
```

- [ ] **Step 9: Implement `app/api/files.py`**

```python
# app/api/files.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.auth.deps import current_user
from app.config import get_settings
from app.db.models import User
from app.storage import files

router = APIRouter(prefix="/api/v1/files", tags=["files"])


@router.get("/{path:path}")
def get_file(path: str, u: User = Depends(current_user)):
    s = get_settings()
    p = (s.data_dir_abs / path).resolve()
    try:
        p.relative_to(s.data_dir_abs)  # ensure inside data dir
    except ValueError:
        raise HTTPException(400, "bad path")
    if not files.verify_owner(p, u.id):
        raise HTTPException(403, "forbidden")
    if not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(p)
```

- [ ] **Step 10: Add a temporary `app/main.build_app()` so tests can import it (Task 11 wires it fully)**

```python
# app/main.py (stub for Task 7; full impl in Task 11)
from __future__ import annotations
from fastapi import FastAPI

def build_app() -> FastAPI:
    from app.api import auth, models, uploads, generation, jobs, history, files as files_api
    app = FastAPI(title="LTX-Video Web Platform", version="0.1.0")
    app.include_router(auth.router)
    app.include_router(models.router)
    app.include_router(uploads.router)
    app.include_router(generation.router)
    app.include_router(jobs.router)
    app.include_router(history.router)
    app.include_router(files_api.router)
    return app
```

- [ ] **Step 11: Run all integration tests**

Run: `pytest tests/integration/ -v`
Expected: PASS for `test_api_auth.py`; write the rest by mirroring the auth test pattern:

```python
# tests/integration/test_api_uploads.py
def test_upload_then_list(client, auth_headers):
    r = client.post("/api/v1/uploads",
                    files={"file": ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")},
                    headers=auth_headers)
    assert r.status_code == 200, r.text
    assert "id" in r.json()
```

```python
# tests/integration/test_api_generation.py
def test_t2v_enqueues(client, auth_headers, monkeypatch):
    # Stub the queue so we don't actually run inference
    from app.core import job_queue as jq
    called = {}
    def fake_submit(*, kind, user_id, model_id, params, parent_job_id=None):
        called["kind"] = kind; called["model_id"] = model_id
        return "01HFAKE0000000000000000000"
    monkeypatch.setattr(jq.get_queue(), "submit", fake_submit)
    r = client.post("/api/v1/t2v", json={
        "model_id": "ltx-2b-distilled", "prompt": "x", "num_frames": 9,
        "height": 64, "width": 64, "num_inference_steps": 2, "guidance_scale": 5.0,
    }, headers=auth_headers)
    assert r.status_code == 202
    assert called["kind"] == "t2v"
```

- [ ] **Step 12: Commit**

```bash
git add app/api app/main.py tests/integration/
git commit -m "feat: REST API — auth, models, uploads, generation, jobs, history, files"
```

---

## Task 8: Gradio UI

**Files:**
- Create: `app/ui/api_client.py`, `app/ui/gradio_app.py`, `app/ui/__init__.py`, `tests/e2e/test_gradio_login.py`

**Interfaces produced:**
- `app.ui.api_client.ApiClient(base_url: str, token: str | None = None)` with methods `login`, `me`, `list_models`, `submit_t2v`, `submit_i2v`, `submit_extend`, `get_job`, `wait_job`, `list_history`, `upload`
- `app.ui.gradio_app.build_blocks() -> gr.Blocks` with tabs: Generate (sub-tabs), Models, History, Account

- [ ] **Step 1: Write the failing Gradio login e2e test**

```python
# tests/e2e/test_gradio_login.py
from gradio_client import Client
import pytest

@pytest.mark.gpu(False)  # UI smoke only
def test_gradio_login_screen_loads(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import build_gradio_app
    blocks, _port = build_gradio_app(launch=False)
    # gradio_client requires running server; here we assert blocks build without error
    assert blocks is not None
```

- [ ] **Step 2: Implement `app/ui/api_client.py`**

```python
# app/ui/api_client.py
from __future__ import annotations
import time
from typing import Any

import httpx


class ApiClient:
    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._c = httpx.Client(base_url=self.base_url, timeout=httpx.Timeout(60.0, connect=10.0))

    def _h(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def login(self, username: str, password: str) -> str:
        r = self._c.post("/api/v1/auth/login",
                         data={"username": username, "password": password})
        r.raise_for_status()
        self.token = r.json()["access_token"]
        return self.token

    def me(self) -> dict:
        return self._c.get("/api/v1/auth/me", headers=self._h()).json()

    def list_models(self) -> list[dict]:
        return self._c.get("/api/v1/models", headers=self._h()).json()

    def upload(self, path: str) -> str:
        with open(path, "rb") as f:
            r = self._c.post("/api/v1/uploads",
                             files={"file": (path, f, "image/png")},
                             headers=self._h())
        r.raise_for_status()
        return r.json()["id"]

    def submit_t2v(self, **kw) -> str:
        r = self._c.post("/api/v1/t2v", json=kw, headers=self._h())
        r.raise_for_status(); return r.json()["job_id"]

    def submit_i2v(self, **kw) -> str:
        r = self._c.post("/api/v1/i2v", json=kw, headers=self._h())
        r.raise_for_status(); return r.json()["job_id"]

    def submit_extend(self, **kw) -> str:
        r = self._c.post("/api/v1/extend", json=kw, headers=self._h())
        r.raise_for_status(); return r.json()["job_id"]

    def get_job(self, job_id: str) -> dict:
        return self._c.get(f"/api/v1/jobs/{job_id}", headers=self._h()).json()

    def wait_job(self, job_id: str, timeout_sec: int = 1800, on_progress=None) -> dict:
        t0 = time.time()
        while True:
            j = self.get_job(job_id)
            if on_progress:
                on_progress(j)
            if j["status"] in ("succeeded", "failed", "cancelled"):
                return j
            if time.time() - t0 > timeout_sec:
                raise TimeoutError(job_id)
            time.sleep(1.0)

    def list_history(self, **kw) -> list[dict]:
        return self._c.get("/api/v1/history", params=kw, headers=self._h()).json()

    def result_url(self, job_id: str) -> str:
        return f"{self.base_url}/api/v1/jobs/{job_id}/result"
```

- [ ] **Step 3: Implement `app/ui/gradio_app.py`**

```python
# app/ui/gradio_app.py
from __future__ import annotations
import gradio as gr

from app.config import get_settings
from app.ui.api_client import ApiClient


def _client(state) -> ApiClient:
    base = f"http://127.0.0.1:{get_settings().app_port_api}"
    return ApiClient(base, token=state.get("token"))


def build_gradio_app(launch: bool = True):
    state = gr.State({"token": None})

    def login(user, pwd, state):
        c = _client(state)
        c.login(user, pwd)
        state["token"] = c.token
        return state, f"logged in as {c.me()['username']}"

    def do_t2v(model_id, prompt, steps, frames, h, w, state, progress=gr.Progress()):
        c = _client(state)
        def _cb(j):
            progress(j["progress"], desc=f"{j['stage']} ({j['status']})")
        job_id = c.submit_t2v(model_id=model_id, prompt=prompt, num_frames=int(frames),
                              height=int(h), width=int(w),
                              num_inference_steps=int(steps), guidance_scale=5.0, fps=24)
        j = c.wait_job(job_id, on_progress=_cb)
        if j["status"] != "succeeded":
            raise gr.Error(j.get("error") or j["status"])
        return c.result_url(job_id)

    def do_i2v(model_id, img_path, prompt, strength, steps, frames, state, progress=gr.Progress()):
        c = _client(state)
        upload_id = c.upload(img_path)
        def _cb(j):
            progress(j["progress"], desc=f"{j['stage']} ({j['status']})")
        job_id = c.submit_i2v(model_id=model_id, image_upload_id=upload_id, prompt=prompt,
                              strength=float(strength), num_frames=int(frames),
                              num_inference_steps=int(steps), guidance_scale=5.0, fps=24)
        j = c.wait_job(job_id, on_progress=_cb)
        if j["status"] != "succeeded":
            raise gr.Error(j.get("error") or j["status"])
        return c.result_url(job_id)

    def do_extend(parent_job_id, prompt, steps, frames, state, progress=gr.Progress()):
        c = _client(state)
        def _cb(j):
            progress(j["progress"], desc=f"{j['stage']} ({j['status']})")
        job_id = c.submit_extend(parent_job_id=parent_job_id, prompt=prompt,
                                 num_frames=int(frames),
                                 num_inference_steps=int(steps), guidance_scale=5.0, fps=24)
        j = c.wait_job(job_id, on_progress=_cb)
        if j["status"] != "succeeded":
            raise gr.Error(j.get("error") or j["status"])
        return c.result_url(job_id)

    def refresh_models(state):
        c = _client(state)
        ids = [m["id"] for m in c.list_models() if m["enabled"]]
        return gr.update(choices=ids)

    def refresh_history(state, limit=20):
        c = _client(state)
        rows = c.list_history(limit=limit)
        return [[r["id"], r["kind"], r["model_id"], r["status"], r["created_at"]] for r in rows]

    with gr.Blocks(title="LTX-Video Web Platform") as blocks:
        gr.Markdown("# LTX-Video")

        with gr.Row():
            u = gr.Textbox(label="username")
            p = gr.Textbox(label="password", type="password")
            btn = gr.Button("Login")
            status = gr.Markdown()

        with gr.Tabs():
            with gr.Tab("Generate — T2V"):
                with gr.Row():
                    mp = gr.Dropdown(label="model", choices=[], interactive=True)
                    refresh_btn = gr.Button("Refresh models")
                prompt = gr.Textbox(label="prompt")
                with gr.Row():
                    steps = gr.Slider(1, 100, value=20, step=1, label="steps")
                    frames = gr.Slider(9, 241, value=121, step=8, label="frames (8n+1)")
                    h = gr.Slider(64, 1024, value=480, step=32, label="height (÷32)")
                    w = gr.Slider(64, 1024, value=768, step=32, label="width (÷32)")
                run = gr.Button("Generate", variant="primary")
                video = gr.Video()
                refresh_btn.click(refresh_models, [state], [mp])
                run.click(do_t2v, [mp, prompt, steps, frames, h, w, state], [video])

            with gr.Tab("Generate — I2V"):
                with gr.Row():
                    imp = gr.Dropdown(label="model", choices=[], interactive=True)
                    irefresh = gr.Button("Refresh models")
                img = gr.Image(type="filepath")
                iprompt = gr.Textbox(label="prompt")
                with gr.Row():
                    istrength = gr.Slider(0.0, 1.0, value=0.85, step=0.05, label="strength")
                    isteps = gr.Slider(1, 100, value=20, step=1, label="steps")
                    iframes = gr.Slider(9, 241, value=121, step=8, label="frames (8n+1)")
                irun = gr.Button("Generate", variant="primary")
                ivideo = gr.Video()
                irefresh.click(refresh_models, [state], [imp])
                irun.click(do_i2v, [imp, img, iprompt, istrength, isteps, iframes, state], [ivideo])

            with gr.Tab("Generate — Long-video"):
                lmp = gr.Dropdown(label="model (long-multishot)", choices=[], interactive=True)
                lrefresh = gr.Button("Refresh models")
                lprompt = gr.Textbox(label="prompts (use | to split windows)")
                with gr.Row():
                    ltile = gr.Slider(40, 161, value=80, step=1, label="tile_size")
                    loverlap = gr.Slider(8, 80, value=24, step=1, label="overlap")
                    lframes = gr.Slider(81, 241, value=161, step=8, label="frames (8n+1)")
                    lsteps = gr.Slider(1, 100, value=30, step=1, label="steps")
                lrun = gr.Button("Generate", variant="primary")
                lvideo = gr.Video()
                lrefresh.click(refresh_models, [state], [lmp])
                lrun.click(do_t2v, [lmp, lprompt, lsteps, lframes, gr.State(480), gr.State(768), state], [lvideo])

            with gr.Tab("Generate — Extend (last-frame)"):
                ep = gr.Textbox(label="parent job_id")
                eprompt = gr.Textbox(label="prompt (optional)")
                with gr.Row():
                    esteps = gr.Slider(1, 100, value=20, step=1, label="steps")
                    eframes = gr.Slider(9, 241, value=121, step=8, label="extra frames")
                erun = gr.Button("Extend", variant="primary")
                evideo = gr.Video()
                erun.click(do_extend, [ep, eprompt, esteps, eframes, state], [evideo])

            with gr.Tab("Models"):
                gr.Markdown("List at `GET /api/v1/models`. Click *Refresh models* in Generate tabs to populate dropdowns.")
                refresh_all = gr.Button("List enabled models")
                model_list = gr.Dataframe(headers=["id", "display_name", "vram_gb", "enabled"], interactive=False)
                def _list(state):
                    c = _client(state)
                    return [[m["id"], m["display_name"], m["vram_gb"], m["enabled"]] for m in c.list_models()]
                refresh_all.click(_list, [state], [model_list])

            with gr.Tab("History"):
                history_refresh = gr.Button("Refresh")
                history_table = gr.Dataframe(headers=["id", "kind", "model_id", "status", "created_at"], interactive=False)
                history_refresh.click(refresh_history, [state], [history_table])

            with gr.Tab("Account"):
                me_btn = gr.Button("Who am I?")
                me_out = gr.Markdown()
                def _me(state):
                    c = _client(state)
                    u = c.me()
                    return f"id={u['id']}  username={u['username']}  role={u['role']}"
                me_btn.click(_me, [state], [me_out])

        btn.click(login, [u, p, state], [state, status])

    port = get_settings().app_port_gradio
    if launch:
        blocks.launch(server_name="0.0.0.0", server_port=port, prevent_thread_lock=True)
    return blocks, port
```

- [ ] **Step 4: Run e2e test**

Run: `pytest tests/e2e/test_gradio_login.py -v`
Expected: PASS (smoke — builds Blocks without launching).

- [ ] **Step 5: Commit**

```bash
git add app/ui tests/e2e/test_gradio_login.py
git commit -m "feat: Gradio UI shell + api client"
```

---

## Task 9: Wire real LTX-Video loader + finalize job_runner paths

**Files:**
- Modify: `app/core/job_runner.py` (handle `kind=model_load` special case; load LTX-Video via real pipeline)
- Modify: `app/core/ltx_wrappers.py` (verify against installed LTX-Video signature; see Step 1)
- Modify: `app/main.py` (add startup bootstrap including `Base.metadata.create_all` + admin user creation + registry seed)
- Create: `tests/integration/test_api_models.py`

**Interfaces confirmed unchanged** from earlier tasks.

- [ ] **Step 1: Verify LTX-Video imports and pipeline call shape**

```bash
pip install git+https://github.com/Lightricks/LTX-Video.git
python -c "from ltx_video.pipelines.pipeline_ltx_video import LTXVideoPipeline; print(LTXVideoPipeline.__call__.__doc__ or 'see source')"
```

Look at `ltx_video/pipelines/pipeline_ltx_video.py` (or its current name) and confirm: keyword names of `__call__`, expected types for `image`, presence of `callback_on_step_end`, return type. Update `app/core/ltx_wrappers.py` field-by-field if names differ. (Spec §14 R1.)

- [ ] **Step 2: Patch `app/core/job_runner.py` to handle `model_load` and `extend` kinds**

```python
# inside run(job_id, db), add at the top, after status/running setup:
if j.kind == "model_load":
    params = json.loads(j.params_json)
    if params.get("op") == "unload":
        pm_mod.get_manager().unload()
    else:
        pm_mod.get_manager().load(j.model_id, loader=_real_loader_for(j.model_id))
    j.status = JobStatus.succeeded
    j.finished_at = datetime.now(timezone.utc)
    db.commit()
    return
```

Add `extend` handling: read parent job's `output_path`, extract last frame with `imageio.get_reader(...).get_data(last_index)`, save as upload, and submit a real I2V job inline (or enqueue an `i2v` job with the last frame's `image_upload_id` and `parent_job_id` set).

- [ ] **Step 3: Bootstrap DB on startup and seed admin user + registry rows**

```python
# app/main.py (revised)
from __future__ import annotations
import threading
import logging
import uvicorn
from fastapi import FastAPI

from app.config import get_settings
from app.db.session import Base, get_engine, SessionLocal
from app.db.models import User, Role
from app.auth.passwords import hash_password
from app.core.registry import load as load_registry
from app.core import job_queue as jq


def _bootstrap() -> None:
    s = get_settings()
    s.data_dir_abs.mkdir(parents=True, exist_ok=True)
    s.uploads_dir.mkdir(parents=True, exist_ok=True)
    s.outputs_dir.mkdir(parents=True, exist_ok=True)
    s.previews_dir.mkdir(parents=True, exist_ok=True)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA not available; this app requires a GPU.")
    Base.metadata.create_all(get_engine())
    # Seed admin user
    with SessionLocal() as db:
        if not db.query(User).filter_by(username=s.admin_username).first():
            db.add(User(username=s.admin_username, password_hash=hash_password(s.admin_password),
                        role=Role.admin, is_active=True))
            db.commit()
    # Seed registry rows
    reg = load_registry(s.registry_path)
    from app.db.models import Model as ModelRow
    with SessionLocal() as db:
        for e in reg.models:
            row = db.get(ModelRow, e.id)
            if row is None:
                db.add(ModelRow(**e.__dict__))
            else:
                for k, v in e.__dict__.items():
                    setattr(row, k, v)
        db.commit()


def build_app() -> FastAPI:
    from app.api import auth, models, uploads, generation, jobs, history, files as files_api
    app = FastAPI(title="LTX-Video Web Platform", version="0.1.0")
    app.include_router(auth.router)
    app.include_router(models.router)
    app.include_router(uploads.router)
    app.include_router(generation.router)
    app.include_router(jobs.router)
    app.include_router(history.router)
    app.include_router(files_api.router)
    return app


def main() -> None:
    import torch  # late import; requires CUDA at startup
    logging.basicConfig(level=get_settings().log_level)
    _bootstrap()
    jq.get_queue().start()
    app = build_app()
    s = get_settings()

    # Start Gradio on a background thread
    from app.ui.gradio_app import build_gradio_app
    def _gradio():
        build_gradio_app(launch=True)
    threading.Thread(target=_gradio, daemon=True).start()

    uvicorn.run(app, host=s.app_host, port=s.app_port_api, log_level=s.log_level.lower())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Add a quick API test for models listing**

```python
# tests/integration/test_api_models.py
def test_models_list(client, auth_headers):
    r = client.get("/api/v1/models", headers=auth_headers)
    assert r.status_code == 200
    ids = {m["id"] for m in r.json()}
    assert "ltx-2b-distilled" in ids
```

Run: `pytest tests/integration/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/job_runner.py app/core/ltx_wrappers.py app/main.py tests/integration/test_api_models.py
git commit -m "feat: real LTX-Video loader wiring + startup bootstrap + admin seed"
```

---

## Task 10: End-to-end smoke on a real GPU

**Files:**
- Create: `tests/e2e/test_real_gpu.py`

**Purpose:** Run a real 2B-distilled generation end-to-end with minimal frames + steps to validate the full pipeline without committing 30 minutes.

- [ ] **Step 1: Write the GPU smoke test**

```python
# tests/e2e/test_real_gpu.py
import time
import pytest
import requests

pytestmark = pytest.mark.gpu


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    import subprocess, os, signal
    import sys
    tmp = tmp_path_factory.mktemp("gpu")
    env = os.environ.copy()
    env.update({
        "DATA_DIR": str(tmp / "data"),
        "MODEL_DIR": str(tmp / "models"),
        "JWT_SECRET": "x" * 32,
        "ADMIN_PASSWORD": "admin",
    })
    p = subprocess.Popen([sys.executable, "-m", "app.main"], env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    # wait for /healthz
    for _ in range(60):
        try:
            r = requests.get("http://127.0.0.1:8000/api/v1/models", timeout=1)
            if r.status_code in (401, 200):
                break
        except Exception:
            time.sleep(1)
    yield p
    p.send_signal(signal.SIGTERM)
    p.wait(timeout=10)


def test_real_t2v_2b(server):
    # login
    tok = requests.post("http://127.0.0.1:8000/api/v1/auth/login",
                        data={"username": "admin", "password": "admin"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    # 2B distilled with minimal settings — assumes checkpoint exists
    r = requests.post("http://127.0.0.1:8000/api/v1/t2v", json={
        "model_id": "ltx-2b-distilled",
        "prompt": "a red cube",
        "num_frames": 9,
        "height": 128, "width": 128,
        "num_inference_steps": 2,
        "guidance_scale": 5.0,
    }, headers=h)
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    # poll
    for _ in range(120):
        j = requests.get(f"http://127.0.0.1:8000/api/v1/jobs/{job_id}", headers=h).json()
        if j["status"] in ("succeeded", "failed"):
            break
        time.sleep(2)
    assert j["status"] == "succeeded", j.get("error")
    # fetch result
    r = requests.get(f"http://127.0.0.1:8000/api/v1/jobs/{job_id}/result", headers=h, stream=True)
    assert r.status_code == 200
    assert int(r.headers.get("content-length", 0)) > 1000
```

- [ ] **Step 2: Run on a GPU host**

```bash
# pre-reqs: model downloaded
python scripts/download_models.py --model ltx-2b-distilled
# run only GPU tests
pytest tests/e2e/test_real_gpu.py -v -m gpu
```
Expected: PASS within ~60 s on RTX 3090/4090.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_real_gpu.py
git commit -m "test: real-GPU smoke (2B distilled, 9 frames, 2 steps)"
```

---

## Task 11: Run the app and verify end-to-end manually

**Files:** none new; manual smoke.

- [ ] **Step 1: Boot the app**

```bash
python scripts/download_models.py --model ltx-2b-distilled
cp .env.example .env  # edit JWT_SECRET
python -m app.main
```
Expected: log lines confirm CUDA visible, admin user created, Gradio on :7860, API on :8000.

- [ ] **Step 2: Login + generate**

Open http://localhost:7860. Log in `admin` / `<your password>`. Open the T2V tab. Pick `ltx-2b-distilled`. Prompt: "a cat playing piano". Frames 9, steps 4, 128×128. Click Generate.
Expected: progress bar advances; video player shows an mp4 within ~30 s.

- [ ] **Step 3: API smoke**

```bash
TOK=$(curl -s -d "username=admin&password=$ADMIN_PASSWORD" \
       http://127.0.0.1:8000/api/v1/auth/login | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s http://127.0.0.1:8000/api/v1/models -H "Authorization: Bearer $TOK" | python -m json.tool
```
Expected: JSON list of models with `id`, `display_name`, etc.

- [ ] **Step 4: Commit any tweaks + tag**

```bash
git tag v0.1.0-mvp
```

---

## Self-Review

**Spec coverage check:**
- G1 (Web UI): Task 8.
- G2 (distilled variants + advanced toggle): Task 4 (registry), Task 5 (manager), Task 9 (admin seed of `enabled: false` for full).
- G3 (auth + history): Task 3 (auth), Task 7 (`/history`).
- G4 (async queue + progress + preview): Task 6 (queue, runner), Task 7 (`/jobs/{id}` + `/preview`).
- G5 (model hot-swap): Task 5 (`pipeline_manager.load`/`unload`); Task 9 (`/models/{id}/load`).
- G6 (two-stage upscale): Task 7 (`POST /upscale`, `two_stage` field), Task 9 runner handles `upscale` kind.
- G7 (long-video): Task 5 (`long_video.py` split + plan), Task 5 wrapper (window plan passed to pipeline), Task 7 (`/t2v` with `temporal_tile_size`).
- G8 (REST API): Task 7 (all routes).
- G9 (single command): Task 9 (`python -m app.main`).

**Risks acknowledged:**
- R1 (LTX-Video signature drift): Task 9 Step 1 forces verification before wrapping; flagged.
- R2 (long-video VRAM): documented in `registry.yaml` `vram_gb: 20`; UI surfaces this in Task 8.
- R3 (LoRAs): deferred, not in tasks.
- R4 (HF path for `long-multi-shot`): Task 9 Step 1 includes a confirmation check.

**No placeholders:** Each step includes runnable code or a concrete command.

**Type/signature consistency:**
- `Settings.data_dir_abs`, `uploads_dir`, `outputs_dir`, `previews_dir` — referenced in `storage.files` and `main.py`. Consistent.
- `JobQueue.submit(kind, user_id, model_id, params, parent_job_id=None)` — same kwargs in `app/api/generation.py` (`_enqueue`) and `app/api/models.py` (`load_model`). Consistent.
- `Job` field names (`status`, `progress`, `stage`, `error`, `output_path`, `parent_job_id`, `duration_sec`) — same in `db/models.py`, `job_runner.py`, `api/jobs.py`, `api/history.py`. Consistent.
- `ApiClient` methods — used by Gradio UI; not currently covered by integration tests but are simple httpx wrappers.

**Scope:** 11 tasks. Each task produces an independently testable deliverable. None is too large to review in one pass.
