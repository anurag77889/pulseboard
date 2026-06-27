# Phase 1 imports
import json
from fastapi import APIRouter, HTTPException
from redis_client import get_redis
from fake_db import get_user_from_db, update_user_in_db

router = APIRouter(tags=["Phase 1 - Cache"])
r = get_redis()

CACHE_TTL = 60

# Endpoint 1: GET user profile (cache-aside pattern)


@router.get("/users/{user_id}")
def get_user(user_id: str):
    cache_key = f"user:{user_id}"

    cached = r.get(cache_key)

    if cached:
        return {**json.loads(cached), "source": "cache"}

    user = get_user_from_db(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    r.setex(cache_key, CACHE_TTL, json.dumps(user))

    return {**user, "source": "db"}

# Endpoint 2: UPDATE user (cache invalidation)


@router.patch("/users/{user_id}")
def update_user(user_id: str, updates: dict):
    updated = update_user_in_db(user_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    cache_key = f"user:{user_id}"
    r.delete(cache_key)

    return updated

# Endpoint 3: Inspect cache state (learning tool)


@router.get("/cache/inspect/{user_id}")
def inspect_cache(user_id: str):
    cache_key = f"user:{user_id}"

    return {
        "key": cache_key,
        "exists": r.exists(cache_key),
        "ttl_seconds": r.ttl(cache_key),
        "value": r.get(cache_key)
    }
