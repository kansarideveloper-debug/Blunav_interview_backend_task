from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import async_session_factory

router = APIRouter()


@router.get("/healthz")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readiness() -> dict[str, str]:
    async with async_session_factory() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ready"}
