import time

import redis.asyncio as redis

from app.config import get_settings


class RateLimiter:
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    async def check(self, *, key: str, limit_per_minute: int) -> bool:
        if limit_per_minute <= 0:
            return True
        window = int(time.time() // 60)
        redis_key = f"rl:{key}:{window}"
        count = await self._r.incr(redis_key)
        if count == 1:
            await self._r.expire(redis_key, 120)
        return count <= limit_per_minute


_redis: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None


def rate_limiter_from_client(client: redis.Redis) -> RateLimiter:
    return RateLimiter(client)
