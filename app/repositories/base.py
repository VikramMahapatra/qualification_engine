from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class SQLAlchemyRepository(Generic[ModelT]):
    """Thin persistence boundary so services never build queries inline."""

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        return entity

    def get(self, entity_id: str) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def get_for_tenant(self, entity_id: str, tenant_id: str) -> ModelT | None:
        stmt = select(self.model).where(
            self.model.id == entity_id,  # type: ignore[attr-defined]
            self.model.tenant_id == tenant_id,  # type: ignore[attr-defined]
        )
        return self.session.execute(stmt).scalar_one_or_none()
