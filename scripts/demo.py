"""Local demo: provisions a tenant, stores a template and evaluates two transcripts.

    python -m scripts.demo
"""

from __future__ import annotations

import json
import uuid

from app.db.base import Base
from app.db.session import SessionFactory, engine
from app.engine.factory import get_pipeline
from app.schemas.api import EvaluationRequest
from app.services.evaluation_service import EvaluationService
from app.services.template_service import TemplateService
from app.services.tenant_service import TenantService
from tests.factories import build_template, disqualified_transcript, very_hot_transcript


def main() -> None:
    Base.metadata.create_all(bind=engine)
    session = SessionFactory()
    try:
        tenants = TenantService(session)
        tenant, api_key = tenants.create("Demo Co", f"demo-{uuid.uuid4().hex[:8]}")
        print(f"Tenant {tenant.slug} provisioned. API key: {api_key}\n")

        template = build_template()
        record = TemplateService(session).create(tenant.id, "demo-project", template)

        evaluations = EvaluationService(session, get_pipeline())
        for transcript in (very_hot_transcript("demo-conv-1"), disqualified_transcript("demo-conv-2")):
            result = evaluations.evaluate(
                tenant.id,
                EvaluationRequest(
                    project_id="demo-project",
                    transcript=transcript,
                    template_id=record.id,
                ),
            )
            print(f"--- {transcript.conversation_transcript_id} ---")
            print(f"qualified={result.qualified} score={result.score} temperature={result.temperature}")
            print(f"summary: {result.summary}")
            for entry in result.trace:
                print(f"  {entry.order:>2}. {entry.title}: {entry.decision}")
            print()

        print(json.dumps(evaluations.stats(tenant.id).model_dump(), indent=2))
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    main()
