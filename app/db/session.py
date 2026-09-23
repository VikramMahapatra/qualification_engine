from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()


def _prepare_sqlite_path(database_url: str) -> None:
    if not database_url.startswith("sqlite"):
        return
    raw_path = database_url.split("///")[-1]
    if raw_path == ":memory:":
        return
    Path(raw_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


_prepare_sqlite_path(_settings.database_url)

engine: Engine = create_engine(
    _settings.database_url,
    echo=_settings.sql_echo,
    future=True,
    connect_args={"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # pragma: no cover - driver hook
    if not _settings.database_url.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a transactional session."""
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
