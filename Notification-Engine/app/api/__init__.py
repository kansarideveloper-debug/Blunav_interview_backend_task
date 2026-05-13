from fastapi import APIRouter

from app.api import events, health, notifications

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(events.router, prefix="/v1", tags=["events"])
api_router.include_router(notifications.router, prefix="/v1", tags=["notifications"])
