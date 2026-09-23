from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.models.conversation import ConversationRecord
from app.db.models.evaluation import EvaluationFinding, EvaluationRecord
from app.domain.results import EvaluationResult
from app.domain.template import QualificationTemplate
from app.domain.transcript import ConversationTranscript
from app.engine.pipeline import QualificationPipeline
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.tenant_repository import ProjectRepository
from app.schemas.api import EvaluationRequest, EvaluationStatsResponse
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)


class EvaluationService:
    """Application service: resolves inputs, runs the decision flow and records everything."""

    def __init__(self, session: Session, pipeline: QualificationPipeline) -> None:
        self._session = session
        self._pipeline = pipeline
        self._conversations = ConversationRepository(session)
        self._evaluations = EvaluationRepository(session)
        self._projects = ProjectRepository(session)
        self._templates = TemplateService(session)

    def evaluate(self, tenant_id: str, request: EvaluationRequest) -> EvaluationResult:
        template, template_id = self._resolve_template(tenant_id, request)
        self._projects.get_or_create(tenant_id, request.project_id)
        conversation = self._store_conversation(tenant_id, request.project_id, request.transcript)

        result = self._pipeline.run(
            tenant_id=tenant_id,
            project_id=request.project_id,
            transcript=request.transcript,
            template=template,
        )
        self._store_evaluation(result, conversation, template, template_id)
        logger.info(
            "Evaluation %s for project %s: %s score=%s temperature=%s",
            result.evaluation_id,
            result.project_id,
            result.status,
            result.score,
            result.temperature,
        )
        return result

    def get(self, tenant_id: str, evaluation_id: str) -> EvaluationResult:
        record = self._evaluations.get_for_tenant(evaluation_id, tenant_id)
        if record is None:
            raise NotFoundError(f"Evaluation '{evaluation_id}' not found")
        return EvaluationResult.model_validate(record.result)

    def list(
        self,
        tenant_id: str,
        *,
        project_id: str | None = None,
        conversation_transcript_id: str | None = None,
        qualified: bool | None = None,
        temperature: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EvaluationRecord], int]:
        filters = {
            "project_id": project_id,
            "conversation_transcript_id": conversation_transcript_id,
            "qualified": qualified,
            "temperature": temperature,
        }
        records = self._evaluations.list_for_tenant(tenant_id, limit=limit, offset=offset, **filters)
        total = self._evaluations.count_for_tenant(tenant_id, **filters)
        return records, total

    def stats(self, tenant_id: str, project_id: str | None = None) -> EvaluationStatsResponse:
        total = self._evaluations.count_for_tenant(tenant_id, project_id=project_id)
        qualified = self._evaluations.count_for_tenant(tenant_id, project_id=project_id, qualified=True)
        return EvaluationStatsResponse(
            total_evaluations=total,
            qualified=qualified,
            not_qualified=total - qualified,
            qualification_rate=round(qualified / total, 4) if total else 0.0,
            average_qualified_score=self._evaluations.average_score(tenant_id, project_id),
            temperature_distribution=self._evaluations.temperature_distribution(tenant_id, project_id),
        )

    # -- internals ---------------------------------------------------------------------

    def _resolve_template(
        self, tenant_id: str, request: EvaluationRequest
    ) -> tuple[QualificationTemplate, str | None]:
        if request.template is not None:
            return request.template, None
        assert request.template_id is not None  # guaranteed by request validation
        record = self._templates.get(tenant_id, request.template_id)
        return TemplateService.to_domain(record), record.id

    def _store_conversation(
        self, tenant_id: str, project_id: str, transcript: ConversationTranscript
    ) -> ConversationRecord:
        payload = transcript.model_dump(mode="json")
        existing = self._conversations.find(
            tenant_id, project_id, transcript.conversation_transcript_id
        )
        if existing is not None:
            existing.payload = payload
            existing.message_count = len(transcript.messages)
            existing.channel = transcript.channel
            existing.language = transcript.language
            return existing
        return self._conversations.add(
            ConversationRecord(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_transcript_id=transcript.conversation_transcript_id,
                channel=transcript.channel,
                language=transcript.language,
                message_count=len(transcript.messages),
                payload=payload,
            )
        )

    def _store_evaluation(
        self,
        result: EvaluationResult,
        conversation: ConversationRecord,
        template: QualificationTemplate,
        template_id: str | None,
    ) -> EvaluationRecord:
        serialized = result.model_dump(mode="json")
        record = EvaluationRecord(
            id=result.evaluation_id,
            tenant_id=result.tenant_id,
            project_id=result.project_id,
            conversation_id=conversation.id,
            conversation_transcript_id=result.conversation_transcript_id,
            template_id=template_id,
            template_name=result.template_name,
            template_version=result.template_version,
            template_snapshot=template.model_dump(mode="json"),
            status=str(result.status),
            qualified=result.qualified,
            outcome=str(result.outcome),
            score=result.score,
            temperature=result.temperature,
            summary=result.summary,
            analyzer=self._pipeline.analyzer_name,
            engine_version=result.engine_version,
            duration_ms=result.duration_ms,
            result=serialized,
            trace=serialized["trace"],
        )
        record.findings = list(self._build_findings(result))
        return self._evaluations.add(record)

    @staticmethod
    def _build_findings(result: EvaluationResult):
        for hit in result.disqualifications:
            yield EvaluationFinding(
                kind="disqualification",
                key=hit.key,
                label=hit.label,
                positive=False,
                value=str(hit.severity),
                weight=hit.penalty,
                confidence=1.0,
                evidence=[e.model_dump(mode="json") for e in hit.evidence],
            )
        for requirement in result.requirements.outcomes:
            yield EvaluationFinding(
                kind="requirement",
                key=requirement.key,
                label=requirement.label,
                positive=requirement.met,
                value=str(requirement.kind),
                weight=requirement.weight,
                confidence=requirement.confidence,
                evidence=[e.model_dump(mode="json") for e in requirement.evidence],
            )
        for attribute in result.attributes.outcomes:
            yield EvaluationFinding(
                kind="attribute",
                key=attribute.key,
                label=attribute.label,
                positive=attribute.captured,
                value=None if attribute.value is None else str(attribute.value)[:500],
                weight=attribute.weight,
                confidence=attribute.fit_score,
                evidence=[e.model_dump(mode="json") for e in attribute.evidence],
            )
        for signal in result.signals.outcomes:
            yield EvaluationFinding(
                kind="positive_signal",
                key=signal.key,
                label=signal.label,
                positive=signal.detected,
                value=str(signal.category),
                weight=1.0,
                confidence=signal.confidence,
                evidence=[e.model_dump(mode="json") for e in signal.evidence],
            )
