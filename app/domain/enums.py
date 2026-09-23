from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return str(self.value)


class SpeakerRole(StrEnum):
    CUSTOMER = "customer"
    AGENT = "agent"
    SYSTEM = "system"


class RequirementKind(StrEnum):
    ESSENTIAL = "essential"
    SUPPORTING = "supporting"


class RequirementPolicy(StrEnum):
    """How the set of Qualified Lead requirements is combined."""

    ESSENTIAL_PLUS_SUPPORTING = "essential_plus_supporting"
    ANY_SELECTED = "any_selected"
    ALL_SELECTED = "all_selected"


class AttributeType(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"


class SignalCategory(StrEnum):
    """Positive signal groups from spec section 11."""

    INTEREST = "interest"
    COMMERCIAL = "commercial"
    NEXT_STEP = "next_step"
    TIMING = "timing"


class ScoreDimension(StrEnum):
    """The five areas the platform scores (spec section 13)."""

    REQUIREMENT = "requirement"
    INTEREST = "interest"
    COMMERCIAL_INTENT = "commercial_intent"
    NEXT_STEP_INTENT = "next_step_intent"
    TIMING = "timing"


class DisqualificationSeverity(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class QualificationStatus(StrEnum):
    QUALIFIED = "qualified"
    NOT_QUALIFIED = "not_qualified"


class EvidenceLevel(StrEnum):
    """Spec section 9 - the engine must not confuse 'no evidence' with 'negative evidence'."""

    SUFFICIENT = "sufficient"
    CONTRADICTED = "contradicted"
    INSUFFICIENT = "insufficient"


class Outcome(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class EvaluationStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStep(StrEnum):
    """Steps of the documented decision flow (2 -> 12)."""

    UNDERSTAND_STATEMENTS = "understand_statements"
    IDENTIFY_SIGNALS = "identify_signals"
    CHECK_DISQUALIFICATION = "check_disqualification"
    EVALUATE_REQUIREMENTS = "evaluate_requirements"
    EVALUATE_ATTRIBUTES = "evaluate_attributes"
    DETERMINE_QUALIFICATION = "determine_qualification"
    EVALUATE_INTENT = "evaluate_intent"
    CALCULATE_SCORE = "calculate_score"
    APPLY_TEMPERATURE_RANGE = "apply_temperature_range"
    FINAL_RESULT = "final_result"
