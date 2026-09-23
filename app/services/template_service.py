from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.template import TemplateRecord
from app.domain.template import QualificationTemplate
from app.repositories.template_repository import TemplateRepository
from app.repositories.tenant_repository import ProjectRepository


class TemplateService:
    def __init__(self, session: Session) -> None:
        self._templates = TemplateRepository(session)
        self._projects = ProjectRepository(session)

    def create(self, tenant_id: str, project_id: str, template: QualificationTemplate) -> TemplateRecord:
        if self._templates.find(tenant_id, project_id, template.name, template.version) is not None:
            raise ConflictError(
                f"Template '{template.name}' version '{template.version}' already exists for this project"
            )
        self._projects.get_or_create(tenant_id, project_id)
        return self._templates.add(
            TemplateRecord(
                tenant_id=tenant_id,
                project_id=project_id,
                name=template.name,
                version=template.version,
                payload=template.model_dump(mode="json"),
            )
        )

    def get(self, tenant_id: str, template_id: str) -> TemplateRecord:
        record = self._templates.get_for_tenant(template_id, tenant_id)
        if record is None:
            raise NotFoundError(f"Template '{template_id}' not found")
        return record

    def list(self, tenant_id: str, project_id: str | None = None) -> list[TemplateRecord]:
        return self._templates.list_for_project(tenant_id, project_id)

    def deactivate(self, tenant_id: str, template_id: str) -> TemplateRecord:
        record = self.get(tenant_id, template_id)
        record.is_active = False
        return record

    @staticmethod
    def to_domain(record: TemplateRecord) -> QualificationTemplate:
        return QualificationTemplate.model_validate(record.payload)
