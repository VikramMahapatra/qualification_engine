from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.tenant import Tenant
from app.engine.pipeline import QualificationPipeline
from app.schemas.api import EvaluationRequest
from app.services.evaluation_service import EvaluationService
from app.services.template_service import TemplateService
from app.services.tenant_service import TenantService
from scripts.migrate_sqlite_to_postgres import (
    MigrationError, copy_rows, open_snapshot, snapshot_sqlite,
)
from tests.factories import build_template, very_hot_transcript


@pytest.fixture
def migration_databases(tmp_path: Path):
    source_path = tmp_path / "source.db"
    source = create_engine(f"sqlite:///{source_path.as_posix()}")
    destination = create_engine(f"sqlite:///{(tmp_path / 'destination.db').as_posix()}")
    Base.metadata.create_all(source)
    Base.metadata.create_all(destination)
    with Session(source) as session:
        tenant, _ = TenantService(session).create("Migration test", "migration-test")
        template = build_template()
        template.campaign_objective.objective = "Unicode migration: café 日本語"
        stored_template = TemplateService(session).create(tenant.id, "migration-project", template)
        EvaluationService(session, QualificationPipeline()).evaluate(
            tenant.id,
            EvaluationRequest(
                project_id="migration-project", template_id=stored_template.id,
                transcript=very_hot_transcript(),
            ),
        )
        session.commit()
    yield source_path, source, destination
    source.dispose()
    destination.dispose()


def test_migration_preserves_all_rows_and_is_repeatable(migration_databases, tmp_path: Path):
    source_path, source, destination = migration_databases
    backup = snapshot_sqlite(source_path, tmp_path / "backups")
    snapshot = open_snapshot(backup)
    try:
        with snapshot.connect() as original, destination.begin() as target:
            report = copy_rows([original], target, batch_size=2)
        assert set(report) == set(Base.metadata.tables)
        assert all(counts["inserted"] == counts["source"] > 0 for counts in report.values())
        with snapshot.connect() as original, destination.begin() as target:
            repeated = copy_rows([original], target, batch_size=2)
        assert all(counts["inserted"] == 0 for counts in repeated.values())
        assert all(counts["unchanged"] == counts["source"] for counts in repeated.values())
        with source.connect() as original, destination.connect() as target:
            for table in Base.metadata.sorted_tables:
                assert original.scalar(select(func.count()).select_from(table)) == target.scalar(
                    select(func.count()).select_from(table)
                )
    finally:
        snapshot.dispose()


def test_migration_dry_run_rolls_back_all_data(migration_databases):
    _, source, destination = migration_databases
    with source.connect() as original, destination.connect() as target:
        transaction = target.begin()
        copy_rows([original], target)
        transaction.rollback()
        for table in Base.metadata.sorted_tables:
            assert target.scalar(select(func.count()).select_from(table)) == 0


def test_conflicting_existing_data_is_not_overwritten(migration_databases):
    _, source, destination = migration_databases
    with source.connect() as original, destination.begin() as target:
        copy_rows([original], target)
    with destination.begin() as target:
        target.execute(Tenant.__table__.update().values(name="Do not overwrite"))
    with pytest.raises(MigrationError, match="Conflicting existing row"):
        with source.connect() as original, destination.begin() as target:
            copy_rows([original], target)
    with destination.connect() as target:
        assert target.scalar(select(Tenant.name)) == "Do not overwrite"


def test_unique_conflict_rolls_back_preceding_rows(migration_databases):
    _, source, destination = migration_databases
    with source.begin() as original:
        original.execute(Tenant.__table__.insert(), [
            {"id": "000-new", "name": "First", "slug": "first", "api_key_hash": "a" * 64},
            {"id": "zzz-conflict", "name": "Conflict", "slug": "duplicate", "api_key_hash": "b" * 64},
        ])
    with destination.begin() as target:
        target.execute(Tenant.__table__.insert().values(
            id="keep", name="Existing", slug="duplicate", api_key_hash="c" * 64,
        ))
    with pytest.raises(IntegrityError):
        with source.connect() as original, destination.begin() as target:
            copy_rows([original], target, batch_size=1)
    with destination.connect() as target:
        assert target.scalar(select(func.count()).select_from(Tenant)) == 1
        assert target.scalar(select(Tenant.id)) == "keep"


def test_missing_source_does_not_create_database(tmp_path: Path):
    missing = tmp_path / "missing.db"
    with pytest.raises(MigrationError, match="does not exist"):
        snapshot_sqlite(missing, tmp_path / "backups")
    assert not missing.exists()


def test_unknown_source_table_is_rejected(migration_databases):
    _, source, destination = migration_databases
    with source.begin() as original:
        original.exec_driver_sql("CREATE TABLE legacy_data (id TEXT)")
    with pytest.raises(MigrationError, match="unknown tables"):
        with source.connect() as original, destination.begin() as target:
            copy_rows([original], target)