from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models.tenant import Project, Tenant
from app.repositories.base import SQLAlchemyRepository


class TenantRepository(SQLAlchemyRepository[Tenant]):
    model = Tenant

    def get_by_slug(self, slug: str) -> Tenant | None:
        return self.session.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none()

    def get_by_api_key_hash(self, api_key_hash: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.api_key_hash == api_key_hash, Tenant.is_active.is_(True))
        return self.session.execute(stmt).scalar_one_or_none()

    def list_all(self) -> list[Tenant]:
        return list(self.session.execute(select(Tenant).order_by(Tenant.created_at)).scalars())


class ProjectRepository(SQLAlchemyRepository[Project]):
    model = Project

    def get_by_external_id(self, tenant_id: str, external_id: str) -> Project | None:
        stmt = select(Project).where(Project.tenant_id == tenant_id, Project.external_id == external_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_or_create(self, tenant_id: str, external_id: str) -> Project:
        existing = self.get_by_external_id(tenant_id, external_id)
        if existing is not None:
            return existing
        if self.session.get_bind().dialect.name == "postgresql":
            # Another request may create this project after our initial SELECT.
            stmt = (
                pg_insert(Project)
                .values(tenant_id=tenant_id, external_id=external_id)
                .on_conflict_do_nothing(constraint="uq_projects_tenant_external")
                .returning(Project)
            )
            created = self.session.execute(stmt).scalar_one_or_none()
            if created is not None:
                return created
            existing = self.get_by_external_id(tenant_id, external_id)
            assert existing is not None
            return existing
        return self.add(Project(tenant_id=tenant_id, external_id=external_id))
