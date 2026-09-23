from __future__ import annotations

from app.domain.enums import DisqualificationSeverity, PipelineStep, ScoreDimension
from app.domain.results import ScoreBreakdown, ScoreComponent
from app.engine.context import EvaluationContext
from app.engine.scoring_model import MAX_SCORE, MIN_SCORE, normalized_weights
from app.engine.steps.base import DecisionStep


class CalculateScoreStep(DecisionStep):
    """Step 9 - calculate the 1-100 lead score using the platform-owned scoring model.

    Spec section 13: requirement, interest, commercial intent, next-step intent and timing.
    """

    step = PipelineStep.CALCULATE_SCORE

    def execute(self, context: EvaluationContext) -> None:
        requirements = context.requirements
        attributes = context.attributes
        signals = context.signals
        assert requirements and attributes and signals

        ratios: dict[ScoreDimension, float] = {
            ScoreDimension.REQUIREMENT: self._requirement_ratio(context)
        }
        ratios.update(signals.dimension_coverage)

        weights = normalized_weights(set(ratios))
        components = [
            ScoreComponent(
                dimension=dimension,
                weight=round(weight, 4),
                ratio=ratios[dimension],
                contribution=round(weight * ratios[dimension] * 100, 2),
            )
            for dimension, weight in weights.items()
        ]

        raw_score = round(sum(c.contribution for c in components), 2)
        penalty = round(
            sum(
                hit.penalty
                for hit in context.disqualifications
                if hit.severity is DisqualificationSeverity.SOFT
            ),
            2,
        )
        final_score = int(round(max(float(MIN_SCORE), min(float(MAX_SCORE), raw_score - penalty))))

        context.score_breakdown = ScoreBreakdown(
            components=components,
            raw_score=raw_score,
            penalty=penalty,
            final_score=final_score,
        )
        context.score = final_score
        context.add_trace(
            self.step,
            "Calculate Lead Score",
            f"Lead score {final_score}/100 (raw {raw_score}, penalty {penalty})",
            {
                str(c.dimension): {"weight": c.weight, "ratio": c.ratio, "points": c.contribution}
                for c in components
            },
        )

    @staticmethod
    def _requirement_ratio(context: EvaluationContext) -> float:
        """How clearly the customer demonstrated a genuine, matching requirement."""
        requirements = context.requirements
        attributes = context.attributes
        assert requirements and attributes
        relevant_attributes = [o for o in attributes.outcomes if o.qualification_relevant]
        if not relevant_attributes:
            return requirements.coverage
        return round((requirements.coverage * 2 + attributes.coverage) / 3, 4)
