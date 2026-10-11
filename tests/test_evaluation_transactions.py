from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.conversation import ConversationRecord
from app.db.models.evaluation import EvaluationRecord
from app.engine.pipeline import QualificationPipeline
from app.schemas.api import EvaluationRequest
from app.services.evaluation_service import EvaluationService
from app.services.tenant_service import TenantService
from tests.factories import build_template, very_hot_transcript


def test_api_analysis_runs_without_transaction_or_writes(session: Session):
    tenant, _ = TenantService(session).create("Transaction test", "transaction-test")
    tenant_id = tenant.id
    session.commit()
    session.execute(select(ConversationRecord))
    assert session.in_transaction()

    class CheckingPipeline(QualificationPipeline):
        def run(self, **kwargs):
            assert not session.in_transaction()
            assert not session.new
            return super().run(**kwargs)

    result = EvaluationService(
        session, CheckingPipeline(), release_read_transaction=True
    ).evaluate(
        tenant_id,
        EvaluationRequest(
            project_id="transaction-project",
            transcript=very_hot_transcript(),
            template=build_template(),
        ),
    )
    assert result.qualified
    # The outer transaction still owns persistence, so rollback removes all writes.
    session.rollback()
    assert session.scalar(select(func.count()).select_from(ConversationRecord)) == 0
    assert session.scalar(select(func.count()).select_from(EvaluationRecord)) == 0