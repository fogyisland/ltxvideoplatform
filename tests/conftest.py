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
