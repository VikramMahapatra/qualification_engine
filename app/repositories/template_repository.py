from __future__ import annotations

from sqlalchemy import select

from app.db.models.template import TemplateRecord
from app.repositories.base import SQLAlchemyRepository


class TemplateRepository(SQLAlchemyRepository[TemplateRecord]):
    model = TemplateRecord

    def find(
        self, tenant_id: str, project_id: str, name: str, version: str
    ) -> TemplateRecord | None:
        stmt = select(TemplateRecord).where(
            TemplateRecord.tenant_id == tenant_id,
            TemplateRecord.project_id == project_id,
            TemplateRecord.name == name,
            TemplateRecord.version == version,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_for_project(
        self, tenant_id: str, project_id: str | None = None, active_only: bool = False
    ) -> list[TemplateRecord]:
        stmt = select(TemplateRecord).where(TemplateRecord.tenant_id == tenant_id)
        if project_id is not None:
            stmt = stmt.where(TemplateRecord.project_id == project_id)
        if active_only:
            stmt = stmt.where(TemplateRecord.is_active.is_(True))
        return list(self.session.execute(stmt.order_by(TemplateRecord.created_at.desc())).scalars())
