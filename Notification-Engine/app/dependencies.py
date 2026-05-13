from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_session
from app.services.messaging import MessageBroker, get_broker
from app.services.rate_limit import RateLimiter, get_redis


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


def message_broker() -> MessageBroker:
    return get_broker()


async def rate_limit(request: Request) -> None:
    settings = get_settings()
    client = await get_redis()
    limiter = RateLimiter(client)
    ip = request.client.host if request.client else "anonymous"
    if not await limiter.check(key=ip, limit_per_minute=settings.api_rate_limit_per_minute):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def idempotency_header(
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> str | None:
    return x_idempotency_key
