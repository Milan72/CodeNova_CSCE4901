"""Shared database configuration and request-scoped sessions."""

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Shared declarative base for application models."""


def create_db_engine() -> Engine:
    """Read DATABASE_URL, defaulting to a SQLite file inside backend/."""
    default_path = Path(__file__).resolve().parents[1] / "code_nova.db"
    url = make_url(os.getenv("DATABASE_URL", f"sqlite:///{default_path}"))
    connect_args = (
        {"check_same_thread": False} if url.get_backend_name() == "sqlite" else {}
    )
    return create_engine(url, connect_args=connect_args, hide_parameters=True)


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a session for FastAPI Depends(get_db), closing it on every exit."""
    with SessionLocal() as session:
        yield session
