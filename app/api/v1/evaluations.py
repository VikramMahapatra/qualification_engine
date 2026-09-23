from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentTenant, EvaluationServiceDep
from app.domain.results import EvaluationResult
from app.schemas.api import EvaluationListItem, EvaluationListResponse, EvaluationRequest, EvaluationStatsResponse

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("", response_model=EvaluationResult, status_code=status.HTTP_201_CREATED)
def evaluate(
    payload: EvaluationRequest, tenant: CurrentTenant, service: EvaluationServiceDep
) -> EvaluationResult:
    """Run the complete qualification & lead scoring decision flow for one conversation."""
    return service.evaluate(tenant.id, payload)


@router.get("", response_model=EvaluationListResponse)
def list_evaluations(
    tenant: CurrentTenant,
    service: EvaluationServiceDep,
    project_id: str | None = Query(default=None),
    conversation_transcript_id: str | None = Query(default=None),
    qualified: bool | None = Query(default=None),
    temperature: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> EvaluationListResponse:
    records, total = service.list(
        tenant.id,
        project_id=project_id,
        conversation_transcript_id=conversation_transcript_id,
        qualified=qualified,
        temperature=temperature,
        limit=limit,
        offset=offset,
    )
    return EvaluationListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[EvaluationListItem.model_validate(r) for r in records],
    )


@router.get("/stats", response_model=EvaluationStatsResponse)
def evaluation_stats(
    tenant: CurrentTenant,
    service: EvaluationServiceDep,
    project_id: str | None = Query(default=None),
) -> EvaluationStatsResponse:
    return service.stats(tenant.id, project_id)


@router.get("/{evaluation_id}", response_model=EvaluationResult)
def get_evaluation(
    evaluation_id: str, tenant: CurrentTenant, service: EvaluationServiceDep
) -> EvaluationResult:
    return service.get(tenant.id, evaluation_id)
