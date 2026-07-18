from redis.asyncio import Redis, from_url

from app.config import get_settings

settings = get_settings()

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = from_url(settings.redis_url, decode_responses=True)
    return _redis


async def check_redis_ok() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception:
        return False
