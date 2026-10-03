from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import SpeakerRole


class MatchRule(BaseModel):
    """Declarative rule describing how a concept is detected in a transcript.

    All populated clauses must hold for the rule to match.
    """

    model_config = ConfigDict(extra="forbid")

    any_of: list[str] = Field(default_factory=list, description="Phrases; at least `min_any` must appear.")
    all_of: list[str] = Field(default_factory=list, description="Phrases that must all appear.")
    none_of: list[str] = Field(default_factory=list, description="Phrases that must not appear.")
    regex: list[str] = Field(default_factory=list, description="Regex patterns; at least one must match.")
    min_any: int = Field(default=1, ge=1)
    case_sensitive: bool = False
    speakers: list[SpeakerRole] = Field(
        default_factory=lambda: [SpeakerRole.CUSTOMER],
        description="Transcript speakers whose messages are searched.",
    )

    @model_validator(mode="after")
    def _at_least_one_clause(self) -> "MatchRule":
        if not (self.any_of or self.all_of or self.none_of or self.regex):
            raise ValueError("MatchRule requires at least one of: any_of, all_of, none_of, regex")
        if self.any_of and self.min_any > len(self.any_of):
            raise ValueError("min_any cannot exceed the number of any_of phrases")
        return self


class Evidence(BaseModel):
    """A single piece of transcript proof supporting a decision."""

    model_config = ConfigDict(extra="forbid")

    message_index: int
    speaker: SpeakerRole
    quote: str
    matched_term: str


class RuleConcept(BaseModel):
    """What a rule means in business terms, for analyzers that judge meaning rather than wording."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(description="e.g. 'qualification requirement', 'positive signal'.")
    label: str
    description: str | None = None
    category: str | None = None
    campaign_objective: str | None = None


class MatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matched: bool
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    evidence: list[Evidence] = Field(default_factory=list)
    reason: str = ""

    @classmethod
    def no_match(cls, reason: str) -> "MatchResult":
        return cls(matched=False, confidence=0.0, reason=reason)
