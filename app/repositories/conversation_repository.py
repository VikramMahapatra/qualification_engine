from __future__ import annotations

from sqlalchemy import select

from app.db.models.conversation import ConversationRecord
from app.repositories.base import SQLAlchemyRepository


class ConversationRepository(SQLAlchemyRepository[ConversationRecord]):
    model = ConversationRecord

    def find(self, tenant_id: str, project_id: str, transcript_id: str) -> ConversationRecord | None:
        stmt = select(ConversationRecord).where(
            ConversationRecord.tenant_id == tenant_id,
            ConversationRecord.project_id == project_id,
            ConversationRecord.conversation_transcript_id == transcript_id,
        )
        return self.session.execute(stmt).scalar_one_or_none()
