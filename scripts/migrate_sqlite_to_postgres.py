"""Copy SQLite application data to configured PostgreSQL without overwriting rows.

Run from the project root with ``python -m scripts.migrate_sqlite_to_postgres``.
Repeat --source to merge multiple databases. --dry-run validates then rolls back.
Stop application writers during migration for a clean cutover.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import uuid
from contextlib import ExitStack, closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Engine, Table, create_engine, func, inspect, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.base import Base
import app.db.models  # noqa: F401 -- register every application table

ROOT = Path(__file__).resolve().parents[1]


class MigrationError(RuntimeError):
    """A safe, non-sensitive migration failure message."""


def snapshot_sqlite(source: Path, backup_dir: Path) -> Path:
    """Use SQLite's online backup API, including committed WAL data."""
    source = source.resolve()
    if not source.is_file():
        raise MigrationError(f"SQLite source does not exist: {source.name}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    backup = backup_dir / f"{source.stem}-{stamp}-{uuid.uuid4().hex[:8]}.db"
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
        with closing(sqlite3.connect(backup)) as copied:
            original.backup(copied)
            if copied.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise MigrationError(f"SQLite integrity check failed: {source.name}")
            if copied.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise MigrationError(f"SQLite contains invalid foreign keys: {source.name}")
    return backup


def open_snapshot(path: Path) -> Engine:
    return create_engine(
        "sqlite://",
        creator=lambda: sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True),
    )


def validate_schema(connection: Connection, *, source: bool) -> None:
    inspector = inspect(connection)
    expected = set(Base.metadata.tables)
    actual = set(inspector.get_table_names())
    missing = expected - actual
    unexpected = actual - expected if source else set()
    if missing or unexpected:
        raise MigrationError(
            f"{'Source' if source else 'Destination'} schema mismatch: "
            f"missing tables={sorted(missing)}, unknown tables={sorted(unexpected)}"
        )
    for table in Base.metadata.sorted_tables:
        expected_columns = set(table.columns.keys())
        actual_columns = {column["name"] for column in inspector.get_columns(table.name)}
        if not expected_columns.issubset(actual_columns) or (source and expected_columns != actual_columns):
            raise MigrationError(f"Column mismatch in table '{table.name}'; migrate its schema first")


def normalize_row(table: Table, row: dict[str, Any]) -> dict[str, Any]:
    """SQLite stores naive timestamps; application timestamps are UTC."""
    normalized = dict(row)
    for column in table.columns:
        value = normalized[column.name]
        if isinstance(column.type, DateTime) and value is not None:
            normalized[column.name] = (
                value.replace(tzinfo=timezone.utc)
                if value.tzinfo is None else value.astimezone(timezone.utc)
            )
    return normalized


def copy_rows(
    sources: list[Connection], destination: Connection, *, batch_size: int = 500
) -> dict[str, dict[str, int]]:
    """Copy and verify every row inside the caller-owned destination transaction."""
    if batch_size < 1:
        raise MigrationError("Batch size must be positive")
    for source in sources:
        validate_schema(source, source=True)
    validate_schema(destination, source=False)
    if destination.dialect.name == "postgresql":
        destination.execute(text("SET LOCAL lock_timeout = '15s'"))
        # Prevent application writers from changing rows between checks and commit.
        names = ", ".join(
            destination.dialect.identifier_preparer.quote(table.name)
            for table in Base.metadata.sorted_tables
        )
        destination.execute(text(f"LOCK TABLE {names} IN SHARE ROW EXCLUSIVE MODE"))
    report: dict[str, dict[str, int]] = {}
    for table in Base.metadata.sorted_tables:
        counts = {"source": 0, "inserted": 0, "unchanged": 0}
        for source in sources:
            expected_count = source.scalar(select(func.count()).select_from(table))
            seen = 0
            result = source.execute(select(table).order_by(table.c.id)).mappings()
            for partition in result.partitions(batch_size):
                rows = [normalize_row(table, dict(row)) for row in partition]
                ids = [row["id"] for row in rows]
                existing = {
                    row["id"]: normalize_row(table, dict(row))
                    for row in destination.execute(select(table).where(table.c.id.in_(ids))).mappings()
                }
                pending = []
                for row in rows:
                    previous = existing.get(row["id"])
                    if previous is None:
                        pending.append(row)
                    elif previous == row:
                        counts["unchanged"] += 1
                    else:
                        raise MigrationError(
                            f"Conflicting existing row in '{table.name}' (ID {row['id']}); "
                            "no rows will be overwritten"
                        )
                if pending:
                    destination.execute(table.insert(), pending)
                    counts["inserted"] += len(pending)
                # Compare every value, not only row counts, before committing.
                stored = {
                    row["id"]: normalize_row(table, dict(row))
                    for row in destination.execute(select(table).where(table.c.id.in_(ids))).mappings()
                }
                if any(stored.get(row["id"]) != row for row in rows):
                    raise MigrationError(f"Data verification failed for '{table.name}'")
                seen += len(rows)
            result.close()
            if seen != expected_count:
                raise MigrationError(f"Source row count changed for '{table.name}'")
            counts["source"] += seen
        report[table.name] = counts
    return report


def migrate(sources: list[Path], *, backup_dir: Path, dry_run: bool, batch_size: int) -> None:
    settings = get_settings()
    url = settings.sqlalchemy_database_url
    if url.get_backend_name() != "postgresql":
        raise MigrationError("Destination must be PostgreSQL; check DB_* or DATABASE_URL settings")
    if batch_size < 1:
        raise MigrationError("Batch size must be positive")
    snapshots = []
    for source in sources:
        backup = snapshot_sqlite(source, backup_dir)
        snapshots.append(backup)
        print(f"Verified SQLite backup: {backup}")
    with ExitStack() as stack:
        connections = []
        for snapshot in snapshots:
            source_engine = open_snapshot(snapshot)
            stack.callback(source_engine.dispose)
            connections.append(stack.enter_context(source_engine.connect()))
        destination_engine = create_engine(
            url, echo=False, hide_parameters=True, pool_pre_ping=True,
            connect_args={"connect_timeout": settings.db_connect_timeout_seconds},
        )
        stack.callback(destination_engine.dispose)
        destination = stack.enter_context(destination_engine.connect())
        transaction = stack.enter_context(destination.begin())
        report = copy_rows(connections, destination, batch_size=batch_size)
        if dry_run:
            transaction.rollback()
        for table, counts in report.items():
            print(
                f"{table}: source={counts['source']}, "
                f"inserted={counts['inserted']}, unchanged={counts['unchanged']}"
            )
    print("Dry run verified; all destination writes rolled back." if dry_run else
          "Migration committed; every source row verified. SQLite originals are unchanged.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, action="append", help="SQLite file; repeat for multiple sources")
    parser.add_argument("--backup-dir", type=Path, default=ROOT / "data" / "migration_backups")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        migrate(
            args.source or [ROOT / "data" / "qualification_engine.db"],
            backup_dir=args.backup_dir, dry_run=args.dry_run, batch_size=args.batch_size,
        )
    except MigrationError as exc:
        print(f"Migration aborted: {exc}", file=sys.stderr)
        return 1
    except (SQLAlchemyError, sqlite3.Error, OSError) as exc:
        original = getattr(exc, "orig", exc)
        # Database exceptions may contain credentials or transcript JSON: never dump them.
        print(
            f"Migration aborted; destination transaction rolled back. "
            f"Database error={type(original).__name__}, SQLSTATE={getattr(original, 'sqlstate', None)}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())