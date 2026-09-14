"""Database engine, session, and Base for Calthem (SQLAlchemy + SQLite)."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from .config import settings

# check_same_thread is a SQLite-only flag; harmless default for other DBs.
_connect_args = {"check_same_thread": False} if settings.DB_URL.startswith("sqlite") else {}

engine = create_engine(settings.DB_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Imported models must be registered before calling."""
    from . import models  # noqa: F401  (ensures models are registered on Base)

    Base.metadata.create_all(bind=engine)
