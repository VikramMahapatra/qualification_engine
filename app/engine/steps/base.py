from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.enums import PipelineStep
from app.engine.context import EvaluationContext


class DecisionStep(ABC):
    """A single stage of the documented decision flow."""

    step: PipelineStep

    @abstractmethod
    def execute(self, context: EvaluationContext) -> None: ...
