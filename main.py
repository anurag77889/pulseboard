import json
from fastapi import FastAPI, HTTPException
from redis_client import get_redis
from fake_db import get_user_from_db, update_user_in_db

import time
from pydantic import BaseModel


app = FastAPI(title="PulseBoard API")
r = get_redis()

CACHE_TTL = 60


# Endpoint 1: GET user profile (cache-aside pattern)

@app.get("/users/{user_id}")
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

@app.patch("/users/{user_id}")
def update_user(user_id: str, updates: dict):
    updated = update_user_in_db(user_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    cache_key = f"user:{user_id}"
    r.delete(cache_key)

    return updated


# Endpoint 3: Inspect cache state (learning tool)

@app.get("/cache/inspect/{user_id}")
def inspect_cache(user_id: str):
    cache_key = f"user:{user_id}"

    return {
        "key": cache_key,
        "exists": r.exists(cache_key),
        "ttl_seconds": r.ttl(cache_key),
        "value": r.get(cache_key)
    }


# Models

class ActionEvent(BaseModel):
    action_type: str        # e.g. "liked_post", "commented"
    target_id: str          # e.g. post_id or user_id
    metadata: dict = {}     # any extra info


FEED_MAX_SIZE = 20          # cap every user's feed at 20 time

# Endpoint 4: Record a user action (WRITE SIDE)


@app.post("/users/{user_id}/actions", status_code=201)
def record_action(user_id: str, event: ActionEvent):
    from fake_db import validate_action

    if not validate_action:
        raise HTTPException(
            status_code=400,
            detail=f"Unknow action: {event.action_type}"
        )

    feed_key = f"feed:{user_id}"

    # Build the event payload - store as JSON string
    payload = json.dumps({
        "action":   event.action_type,
        "target":   event.target_id,
        "meta":     event.metadata,
        "ts":       time.time(),
    })

    # Push this payload to the LEFT of the list
    new_length = r.lpush(feed_key, payload)

    # Cap the list so it never grows beyond FEED_MAX_SIZE
    r.ltrim(feed_key, new_length, FEED_MAX_SIZE - 1)

    return {
        "status":       "recorded",
        "feed_length":  min(new_length, FEED_MAX_SIZE),
    }


# Endpoint 5: Read the activity feed (READ SIDE)


@app.get("/users/{user_id}/feed")
def get_feed(user_id: str, limit: int = 10, offset: int = 0):
    feed_key = f"feed:{user_id}"

    # Fetch 'limit' items starting at 'offset'
    raw_items = r.lrange(feed_key, 0, offset + limit - 1)

    # Deserialize each JSON string back to a dict
    items = [json.loads(item) for item in raw_items]

    # Total feed length
    total = r.llen(feed_key)

    return {
        "user_id":  feed_key,
        "total":    total,
        "offset":   offset,
        "limit":    limit,
        "feed":     items
    }


# Endpoint 7: Clear a user's feed

@app.delete("/users/{user_id}/delete")
def clear_feed(user_id: str):
    feed_key = f"feed:{user_id}"

    deleted = r.delete(feed_key)

    return {"deleted": bool(deleted)}


# Endpoint 8: Peek at feed internals (learning tool)

@app.get("users/{user_id}/feed/debug")
def debug_feed(user_id: str):
    feed_key = f"feed:{user_id}"

    return {
        "key":          feed_key,
        "length":       r.llen(feed_key),
        "first_item":   r.lindex(feed_key, 0),
        "last_item":    r.lindex(feed_key, -1),
        "all_items":    r.lrange(feed_key, 0, -1)
    }
