# app/db/session.py
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
_settings.data_dir_abs.mkdir(parents=True, exist_ok=True)

_engine = create_engine(
    _settings.database_url,
    future=True,
    echo=False,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(
    bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False
)

# Convenience alias for consumers that want the engine directly.
engine = _engine


def get_engine():
    return _engine


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
