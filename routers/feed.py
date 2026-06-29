# Phase 2 imports
import json
import time
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from redis_client import get_redis
from fake_db import validate_action

router = APIRouter(tags=["Phase 2 - Feed"])
r = get_redis()


# Models

class ActionEvent(BaseModel):
    action_type: str        # e.g. "liked_post", "commented"
    target_id: str          # e.g. post_id or user_id
    metadata: dict = {}     # any extra info


FEED_MAX_SIZE = 20          # cap every user's feed at 20 time

# Endpoint 1: Record a user action (WRITE SIDE)


@router.post("/users/{user_id}/actions", status_code=201)
def record_action(user_id: str, event: ActionEvent):

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


# Endpoint 2: Read the activity feed (READ SIDE)


@router.get("/users/{user_id}/feed")
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


# Endpoint 3: Clear a user's feed

@router.delete("/users/{user_id}/delete")
def clear_feed(user_id: str):
    feed_key = f"feed:{user_id}"

    deleted = r.delete(feed_key)

    return {"deleted": bool(deleted)}


# Endpoint 4: Peek at feed internals (learning tool)

@router.get("/users/{user_id}/feed/debug")
def debug_feed(user_id: str):
    feed_key = f"feed:{user_id}"

    return {
        "key":          feed_key,
        "length":       r.llen(feed_key),
        "first_item":   r.lindex(feed_key, 0),
        "last_item":    r.lindex(feed_key, -1),
        "all_items":    r.lrange(feed_key, 0, -1)
    }
