from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.results import EvaluationResult
from app.domain.template import QualificationTemplate
from app.domain.transcript import ConversationTranscript


class TenantCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    is_active: bool
    created_at: datetime


class TenantCreatedResponse(TenantResponse):
    api_key: str = Field(description="Shown once; store it securely.")


class TemplateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=128)
    template: QualificationTemplate


class TemplateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    project_id: str
    name: str
    version: str
    is_active: bool
    created_at: datetime
    template: QualificationTemplate


class EvaluationRequest(BaseModel):
    """The engine's two inputs: a conversation transcript and a qualification template."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=128)
    conversation_transcript_id: str | None = Field(
        default=None,
        max_length=128,
        description="Defaults to the id carried by the transcript.",
    )
    transcript: ConversationTranscript
    template: QualificationTemplate | None = Field(
        default=None, description="Inline six-part template. Mutually exclusive with template_id."
    )
    template_id: str | None = Field(default=None, description="Id of a previously stored template.")

    @model_validator(mode="after")
    def _validate(self) -> "EvaluationRequest":
        if (self.template is None) == (self.template_id is None):
            raise ValueError("Provide exactly one of 'template' or 'template_id'")
        if self.conversation_transcript_id is None:
            self.conversation_transcript_id = self.transcript.conversation_transcript_id
        elif self.conversation_transcript_id != self.transcript.conversation_transcript_id:
            raise ValueError("conversation_transcript_id does not match the transcript")
        return self


class EvaluationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    conversation_transcript_id: str
    template_name: str
    template_version: str
    qualified: bool
    outcome: str
    score: int
    temperature: str | None
    summary: str
    created_at: datetime


class EvaluationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    limit: int
    offset: int
    items: list[EvaluationListItem]


class EvaluationStatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_evaluations: int
    qualified: int
    not_qualified: int
    qualification_rate: float
    average_qualified_score: float
    temperature_distribution: dict[str, int]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


__all__ = [
    "ErrorResponse",
    "EvaluationListItem",
    "EvaluationListResponse",
    "EvaluationRequest",
    "EvaluationResult",
    "EvaluationStatsResponse",
    "TemplateCreateRequest",
    "TemplateResponse",
    "TenantCreateRequest",
    "TenantCreatedResponse",
    "TenantResponse",
]
