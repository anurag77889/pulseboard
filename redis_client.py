import os

import redis

# Use REDIS_URL in production (Render) and fall back to local Redis for development.
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(redis_url, decode_responses=True)


def get_redis():
    return r
