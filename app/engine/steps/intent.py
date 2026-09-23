from __future__ import annotations

from app.domain.enums import PipelineStep, ScoreDimension
from app.domain.results import IntentAssessment, SignalOutcome, SignalsSummary
from app.engine.context import EvaluationContext
from app.engine.scoring_model import INTENT_DIMENSIONS, SIGNAL_CATEGORY_DIMENSION, normalized_weights
from app.engine.steps.base import DecisionStep

_QUESTION_MARK = "?"
_ENGAGEMENT_TARGET_MESSAGES = 6
_ENGAGEMENT_TARGET_WORDS = 120


class EvaluateIntentStep(DecisionStep):
    """Step 8 - evaluate the strength of interest and intent (spec sections 11 and 13)."""

    step = PipelineStep.EVALUATE_INTENT

    def execute(self, context: EvaluationContext) -> None:
        signals_summary = self._build_signals_summary(context)
        context.signals = signals_summary

        customer_messages = context.transcript.customer_messages
        word_count = sum(len(m.text.split()) for m in customer_messages)
        questions = sum(m.text.count(_QUESTION_MARK) for m in customer_messages)

        strength = self._intent_strength(signals_summary)
        drivers = [
            o.label
            for o in signals_summary.outcomes
            if o.detected and SIGNAL_CATEGORY_DIMENSION[o.category] in INTENT_DIMENSIONS
        ]

        context.intent = IntentAssessment(
            strength=strength,
            engagement=self._engagement(len(customer_messages), word_count, questions),
            drivers=drivers,
            customer_message_count=len(customer_messages),
            customer_word_count=word_count,
            questions_asked=questions,
        )
        context.add_trace(
            self.step,
            "Evaluate strength of interest and intent",
            f"Intent strength {strength:.2f}",
            {
                "drivers": drivers,
                "dimension_coverage": {
                    str(k): v for k, v in signals_summary.dimension_coverage.items()
                },
                "signals_detected": signals_summary.detected_count,
                "signals_total": signals_summary.total_count,
            },
        )

    @staticmethod
    def _build_signals_summary(context: EvaluationContext) -> SignalsSummary:
        outcomes: list[SignalOutcome] = []
        for signal in context.template.positive_signals.signals:
            match = context.observations.signal_matches.get(signal.key)
            outcomes.append(
                SignalOutcome(
                    key=signal.key,
                    label=signal.label,
                    category=signal.category,
                    detected=bool(match and match.matched),
                    confidence=match.confidence if match else 0.0,
                    evidence=match.evidence if match else [],
                )
            )

        dimension_coverage: dict[ScoreDimension, float] = {}
        for dimension in {SIGNAL_CATEGORY_DIMENSION[o.category] for o in outcomes}:
            in_dimension = [o for o in outcomes if SIGNAL_CATEGORY_DIMENSION[o.category] is dimension]
            dimension_coverage[dimension] = round(
                sum(1 for o in in_dimension if o.detected) / len(in_dimension), 4
            )

        return SignalsSummary(
            coverage=round(sum(1 for o in outcomes if o.detected) / len(outcomes), 4) if outcomes else 0.0,
            detected_count=sum(1 for o in outcomes if o.detected),
            total_count=len(outcomes),
            dimension_coverage=dimension_coverage,
            outcomes=outcomes,
        )

    @staticmethod
    def _intent_strength(summary: SignalsSummary) -> float:
        active = {d for d in summary.dimension_coverage if d in INTENT_DIMENSIONS}
        if not active:
            return summary.coverage
        weights = normalized_weights(active)
        return round(sum(summary.dimension_coverage[d] * w for d, w in weights.items()), 4)

    @staticmethod
    def _engagement(message_count: int, word_count: int, questions: int) -> float:
        depth = min(1.0, message_count / _ENGAGEMENT_TARGET_MESSAGES)
        verbosity = min(1.0, word_count / _ENGAGEMENT_TARGET_WORDS)
        curiosity = min(1.0, questions / 3)
        return round((0.4 * depth) + (0.4 * verbosity) + (0.2 * curiosity), 4)
