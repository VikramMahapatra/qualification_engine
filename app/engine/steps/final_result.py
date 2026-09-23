from __future__ import annotations

from app.domain.enums import PipelineStep, QualificationStatus
from app.engine.context import EvaluationContext
from app.engine.steps.base import DecisionStep


class FinalResultStep(DecisionStep):
    """Step 12 - compose the final result. Always runs, including after an early halt."""

    step = PipelineStep.FINAL_RESULT

    def execute(self, context: EvaluationContext) -> None:
        if context.status is QualificationStatus.QUALIFIED:
            context.summary = (
                f"Qualified lead with a score of {context.score}/100 "
                f"and a {context.temperature} temperature."
            )
            decision = f"QUALIFIED | score {context.score} | {context.temperature} | {context.outcome}"
        else:
            decision = f"NOT QUALIFIED | {context.outcome} | {context.summary}"

        context.add_trace(
            self.step,
            "Final result",
            decision,
            {
                "qualified": context.status is QualificationStatus.QUALIFIED,
                "score": context.score,
                "temperature": context.temperature,
                "outcome": str(context.outcome),
            },
        )
