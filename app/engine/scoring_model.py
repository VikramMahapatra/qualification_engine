from __future__ import annotations

from app.domain.enums import RequirementKind, ScoreDimension, SignalCategory

# Spec section 14: the platform owns the scoring model. Clients configure business meaning
# (essential vs supporting, signal category), never numeric weights.

DIMENSION_WEIGHTS: dict[ScoreDimension, float] = {
    ScoreDimension.REQUIREMENT: 0.30,
    ScoreDimension.INTEREST: 0.15,
    ScoreDimension.COMMERCIAL_INTENT: 0.25,
    ScoreDimension.NEXT_STEP_INTENT: 0.20,
    ScoreDimension.TIMING: 0.10,
}

SIGNAL_CATEGORY_DIMENSION: dict[SignalCategory, ScoreDimension] = {
    SignalCategory.INTEREST: ScoreDimension.INTEREST,
    SignalCategory.COMMERCIAL: ScoreDimension.COMMERCIAL_INTENT,
    SignalCategory.NEXT_STEP: ScoreDimension.NEXT_STEP_INTENT,
    SignalCategory.TIMING: ScoreDimension.TIMING,
}

IMPORTANCE_WEIGHTS: dict[RequirementKind, float] = {
    RequirementKind.ESSENTIAL: 2.0,
    RequirementKind.SUPPORTING: 1.0,
}

# Dimensions that together express "strength of interest and intent" (spec step 8).
INTENT_DIMENSIONS = (
    ScoreDimension.COMMERCIAL_INTENT,
    ScoreDimension.NEXT_STEP_INTENT,
    ScoreDimension.TIMING,
)

SOFT_DISQUALIFICATION_PENALTY = 15.0

MIN_SCORE = 1
MAX_SCORE = 100


def importance_weight(kind: RequirementKind) -> float:
    return IMPORTANCE_WEIGHTS[kind]


def normalized_weights(active: set[ScoreDimension]) -> dict[ScoreDimension, float]:
    """Weights for the dimensions the template actually configured, renormalized to 1.0.

    A template with no timing signals must not be capped at 90 for the missing dimension.
    """
    selected = {d: w for d, w in DIMENSION_WEIGHTS.items() if d in active}
    total = sum(selected.values())
    if total <= 0:
        return {}
    return {dimension: weight / total for dimension, weight in selected.items()}
