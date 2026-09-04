"""Shared pytest fixtures and configuration."""
from __future__ import annotations

import os

# Environment must be in place before any `app.*` module is imported at
# collection time (app.config.Settings requires a >=32 char JWT_SECRET).
os.environ.setdefault("JWT_SECRET", "t" * 32)
os.environ.setdefault("DEVICE", "cuda")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


@pytest.fixture()
def db_session():
    """In-memory SQLite session with the full schema created from metadata."""
    from app.db import models  # noqa: F401  (register tables)
    from app.db.session import Base

    engine = create_engine(
        "sqlite://", future=True, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """FastAPI TestClient with a fresh DB and seeded admin user."""
    from app.config import get_settings
    from app.db.session import Base, get_engine, SessionLocal
    from app.db.models import User, Role
    from app.auth.passwords import hash_password

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    get_settings.cache_clear()

    # Reset the schema to guarantee a clean DB across test runs.
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    with SessionLocal() as s:
        s.add(User(username="admin", password_hash=hash_password("admin"),
                   role=Role.admin, is_active=True))
        s.commit()

    from app.main import build_app
    from fastapi.testclient import TestClient

    return TestClient(build_app())


@pytest.fixture
def auth_headers(client):
    """Authorization headers for the seeded admin user."""
    r = client.post("/api/v1/auth/login", data={"username": "admin", "password": "admin"})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}
