from __future__ import annotations

from app.domain.enums import PipelineStep
from app.engine.context import EvaluationContext
from app.engine.steps.base import DecisionStep


class ApplyTemperatureStep(DecisionStep):
    """Steps 10 & 11 - apply the configured temperature ranges and assign a temperature."""

    step = PipelineStep.APPLY_TEMPERATURE_RANGE

    def execute(self, context: EvaluationContext) -> None:
        ranges = context.template.temperature_ranges
        band = ranges.resolve(context.score)
        context.temperature = band.name if band else None
        context.add_trace(
            self.step,
            "Apply configured temperature range and assign temperature",
            f"Score {context.score} -> {context.temperature}"
            if band
            else f"Score {context.score} did not fall into any configured band",
            {
                "bands": [
                    {"name": b.name, "min": b.min_score, "max": b.max_score} for b in ranges.bands
                ]
            },
        )
