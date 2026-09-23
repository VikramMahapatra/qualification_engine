from __future__ import annotations

from sqlalchemy import func, select

from app.db.models.evaluation import EvaluationRecord
from app.repositories.base import SQLAlchemyRepository


class EvaluationRepository(SQLAlchemyRepository[EvaluationRecord]):
    model = EvaluationRecord

    def list_for_tenant(
        self,
        tenant_id: str,
        *,
        project_id: str | None = None,
        conversation_transcript_id: str | None = None,
        qualified: bool | None = None,
        temperature: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EvaluationRecord]:
        stmt = select(EvaluationRecord).where(EvaluationRecord.tenant_id == tenant_id)
        stmt = self._apply_filters(stmt, project_id, conversation_transcript_id, qualified, temperature)
        stmt = stmt.order_by(EvaluationRecord.created_at.desc()).limit(limit).offset(offset)
        return list(self.session.execute(stmt).scalars())

    def count_for_tenant(
        self,
        tenant_id: str,
        *,
        project_id: str | None = None,
        conversation_transcript_id: str | None = None,
        qualified: bool | None = None,
        temperature: str | None = None,
    ) -> int:
        stmt = select(func.count(EvaluationRecord.id)).where(EvaluationRecord.tenant_id == tenant_id)
        stmt = self._apply_filters(stmt, project_id, conversation_transcript_id, qualified, temperature)
        return int(self.session.execute(stmt).scalar_one())

    def temperature_distribution(self, tenant_id: str, project_id: str | None = None) -> dict[str, int]:
        stmt = (
            select(EvaluationRecord.temperature, func.count(EvaluationRecord.id))
            .where(EvaluationRecord.tenant_id == tenant_id)
            .group_by(EvaluationRecord.temperature)
        )
        if project_id is not None:
            stmt = stmt.where(EvaluationRecord.project_id == project_id)
        return {row[0] or "unassigned": row[1] for row in self.session.execute(stmt)}

    def average_score(self, tenant_id: str, project_id: str | None = None) -> float:
        stmt = select(func.avg(EvaluationRecord.score)).where(
            EvaluationRecord.tenant_id == tenant_id, EvaluationRecord.qualified.is_(True)
        )
        if project_id is not None:
            stmt = stmt.where(EvaluationRecord.project_id == project_id)
        return round(float(self.session.execute(stmt).scalar() or 0.0), 2)

    @staticmethod
    def _apply_filters(
        stmt,
        project_id: str | None,
        conversation_transcript_id: str | None,
        qualified: bool | None,
        temperature: str | None,
    ):
        if project_id is not None:
            stmt = stmt.where(EvaluationRecord.project_id == project_id)
        if conversation_transcript_id is not None:
            stmt = stmt.where(
                EvaluationRecord.conversation_transcript_id == conversation_transcript_id
            )
        if qualified is not None:
            stmt = stmt.where(EvaluationRecord.qualified.is_(qualified))
        if temperature is not None:
            stmt = stmt.where(EvaluationRecord.temperature == temperature)
        return stmt
