from fastapi import APIRouter

from app.api.v1 import evaluations, health, templates, tenants

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(tenants.router)
api_router.include_router(templates.router)
api_router.include_router(evaluations.router)

__all__ = ["api_router"]
