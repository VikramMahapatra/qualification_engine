from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.engine.analyzer import RuleBasedAnalyzer, TranscriptAnalyzer
from app.engine.llm_analyzer import HybridAnalyzer, LLMAnalyzer
from app.engine.pipeline import QualificationPipeline

logger = logging.getLogger(__name__)


def build_analyzer(settings: Settings | None = None) -> TranscriptAnalyzer:
    settings = settings or get_settings()
    if settings.analyzer == "rule_based":
        return RuleBasedAnalyzer()
    if not settings.openai_api_key:
        logger.warning("ANALYZER=%s but no OpenAI key configured; using rules only", settings.analyzer)
        return RuleBasedAnalyzer()
    llm = LLMAnalyzer(settings)
    return llm if settings.analyzer == "llm" else HybridAnalyzer(llm)


@lru_cache
def get_pipeline() -> QualificationPipeline:
    return QualificationPipeline(analyzer=build_analyzer())
