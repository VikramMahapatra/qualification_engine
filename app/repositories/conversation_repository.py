from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models.conversation import ConversationRecord
from app.domain.transcript import ConversationTranscript
from app.repositories.base import SQLAlchemyRepository


class ConversationRepository(SQLAlchemyRepository[ConversationRecord]):
    model = ConversationRecord

    def store(
        self, tenant_id: str, project_id: str, transcript: ConversationTranscript
    ) -> ConversationRecord:
        values = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "conversation_transcript_id": transcript.conversation_transcript_id,
            "channel": transcript.channel,
            "language": transcript.language,
            "message_count": len(transcript.messages),
            "payload": transcript.model_dump(mode="json"),
        }
        if self.session.get_bind().dialect.name == "postgresql":
            # Atomic upsert prevents concurrent requests racing on transcript identity.
            stmt = pg_insert(ConversationRecord).values(**values)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_conversation_identity",
                set_={
                    key: getattr(stmt.excluded, key)
                    for key in ("channel", "language", "message_count", "payload", "updated_at")
                },
            ).returning(ConversationRecord)
            return self.session.execute(
                stmt, execution_options={"populate_existing": True}
            ).scalar_one()
        existing = self.find(tenant_id, project_id, transcript.conversation_transcript_id)
        if existing is not None:
            existing.channel = transcript.channel
            existing.language = transcript.language
            existing.message_count = len(transcript.messages)
            existing.payload = values["payload"]
            return existing
        return self.add(ConversationRecord(**values))

    def find(self, tenant_id: str, project_id: str, transcript_id: str) -> ConversationRecord | None:
        stmt = select(ConversationRecord).where(
            ConversationRecord.tenant_id == tenant_id,
            ConversationRecord.project_id == project_id,
            ConversationRecord.conversation_transcript_id == transcript_id,
        )
        return self.session.execute(stmt).scalar_one_or_none()
