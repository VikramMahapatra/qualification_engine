from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()
_database_url = _settings.sqlalchemy_database_url
_is_sqlite = _database_url.get_backend_name() == "sqlite"


def _prepare_sqlite_path(database_url: URL) -> None:
    if database_url.get_backend_name() != "sqlite":
        return
    raw_path = database_url.database
    if not raw_path or raw_path == ":memory:":
        return
    Path(raw_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


_prepare_sqlite_path(_database_url)

_engine_options = {}
if _database_url.get_backend_name() == "postgresql":
    _engine_options = {
        "connect_args": {"connect_timeout": _settings.db_connect_timeout_seconds},
        "pool_size": _settings.db_pool_size,
        "max_overflow": _settings.db_max_overflow,
        "pool_timeout": _settings.db_pool_timeout_seconds,
    }
elif _is_sqlite:
    _engine_options = {
        "connect_args": {
            "check_same_thread": False,
            "timeout": _settings.sqlite_timeout_seconds,
        },
    }

engine: Engine = create_engine(
    _database_url,
    echo=_settings.sql_echo,
    future=True,
    pool_pre_ping=True,
    **_engine_options,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # pragma: no cover - driver hook
    if not _is_sqlite:
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
