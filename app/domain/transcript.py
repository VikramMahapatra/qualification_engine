from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import SpeakerRole


class TranscriptMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: SpeakerRole
    text: str = Field(min_length=1)
    timestamp: datetime | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ConversationTranscript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_transcript_id: str = Field(min_length=1, max_length=128)
    channel: str | None = Field(default=None, max_length=64)
    language: str = Field(default="en", max_length=16)
    messages: list[TranscriptMessage] = Field(min_length=1)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("messages")
    @classmethod
    def _needs_customer_input(cls, value: list[TranscriptMessage]) -> list[TranscriptMessage]:
        if not any(m.speaker == SpeakerRole.CUSTOMER for m in value):
            raise ValueError("Transcript must contain at least one customer message")
        return value

    def messages_for(self, speakers: list[SpeakerRole]) -> list[tuple[int, TranscriptMessage]]:
        allowed = set(speakers)
        return [(i, m) for i, m in enumerate(self.messages) if m.speaker in allowed]

    @property
    def customer_messages(self) -> list[TranscriptMessage]:
        return [m for m in self.messages if m.speaker == SpeakerRole.CUSTOMER]
