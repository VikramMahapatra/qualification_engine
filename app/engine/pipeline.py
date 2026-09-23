from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app import __version__
from app.domain.enums import QualificationStatus
from app.domain.results import (
    AttributesSummary,
    EvaluationResult,
    IntentAssessment,
    RequirementsSummary,
    ScoreBreakdown,
    SignalsSummary,
)
from app.domain.template import QualificationTemplate
from app.domain.transcript import ConversationTranscript
from app.engine.analyzer import RuleBasedAnalyzer, TranscriptAnalyzer
from app.engine.context import EvaluationContext
from app.engine.steps import (
    ApplyTemperatureStep,
    CalculateScoreStep,
    CheckDisqualificationStep,
    DecisionStep,
    DetermineQualificationStep,
    EvaluateAttributesStep,
    EvaluateIntentStep,
    EvaluateRequirementsStep,
    FinalResultStep,
    IdentifyObservationsStep,
    UnderstandStatementsStep,
)

logger = logging.getLogger(__name__)


class QualificationPipeline:
    """Executes the complete decision flow (steps 2-12) for one conversation."""

    def __init__(self, analyzer: TranscriptAnalyzer | None = None) -> None:
        self._analyzer = analyzer or RuleBasedAnalyzer()
        self._steps: list[DecisionStep] = [
            UnderstandStatementsStep(),
            IdentifyObservationsStep(),
            CheckDisqualificationStep(),
            EvaluateRequirementsStep(),
            EvaluateAttributesStep(),
            DetermineQualificationStep(),
            EvaluateIntentStep(),
            CalculateScoreStep(),
            ApplyTemperatureStep(),
        ]
        self._final_step = FinalResultStep()

    @property
    def analyzer_name(self) -> str:
        return self._analyzer.name

    def run(
        self,
        *,
        tenant_id: str,
        project_id: str,
        transcript: ConversationTranscript,
        template: QualificationTemplate,
        evaluation_id: str | None = None,
    ) -> EvaluationResult:
        context = EvaluationContext(
            evaluation_id=evaluation_id or str(uuid.uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            transcript=transcript,
            template=template,
            analyzer=self._analyzer,
        )

        for step in self._steps:
            step.execute(context)
            if context.halted:
                logger.info(
                    "Evaluation %s halted at step %s: %s",
                    context.evaluation_id,
                    step.step,
                    context.summary,
                )
                break

        self._final_step.execute(context)
        return self._to_result(context)

    @staticmethod
    def _to_result(context: EvaluationContext) -> EvaluationResult:
        requirements = context.requirements or RequirementsSummary(
            policy=context.template.qualified_lead_requirements.policy,
            satisfied=False,
            essential_met=0,
            essential_total=len(context.template.qualified_lead_requirements.essential()),
            supporting_met=0,
            supporting_total=len(context.template.qualified_lead_requirements.supporting()),
            coverage=0.0,
            explanation="Not evaluated - flow stopped earlier",
        )
        attributes = context.attributes or AttributesSummary(
            satisfied=False, coverage=0.0, missing_essential=[], information_only=[], outcomes=[]
        )
        signals = context.signals or SignalsSummary(
            coverage=0.0,
            detected_count=0,
            total_count=len(context.template.positive_signals.signals),
            outcomes=[],
        )
        intent = context.intent or IntentAssessment(strength=0.0, engagement=0.0)
        breakdown = context.score_breakdown or ScoreBreakdown(
            components=[], raw_score=0.0, penalty=0.0, final_score=context.score
        )

        return EvaluationResult(
            evaluation_id=context.evaluation_id,
            tenant_id=context.tenant_id,
            project_id=context.project_id,
            conversation_transcript_id=context.transcript.conversation_transcript_id,
            template_name=context.template.name,
            template_version=context.template.version,
            status=context.status,
            qualified=context.status is QualificationStatus.QUALIFIED,
            outcome=context.outcome,
            evidence_level=context.evidence_level,
            score=context.score,
            temperature=context.temperature,
            disqualifications=context.disqualifications,
            requirements=requirements,
            attributes=attributes,
            signals=signals,
            intent=intent,
            score_breakdown=breakdown,
            trace=context.trace,
            summary=context.summary,
            engine_version=__version__,
            evaluated_at=datetime.now(timezone.utc),
            duration_ms=context.elapsed_ms,
        )
