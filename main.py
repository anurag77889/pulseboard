# Phase 1 imports
import json
from fastapi import FastAPI, HTTPException
from redis_client import get_redis
from fake_db import get_user_from_db, update_user_in_db

# Phase 2 imports
import time
from pydantic import BaseModel

# Phase 3 imports
from fake_db import LEADERBOARD_SEED

# Phase 4 imports
from fake_db import verify_credentials, generate_session_token

SESSION_TTL = 1800


# Get session data (used by protected endpoints)
def get_session(token: str) -> dict | None:
    session_key = f"session:{token}"

    session_data = r.hgetall(session_key)

    if not session_data:
        return None

    r.expire(session_key, SESSION_TTL)

    return session_data


app = FastAPI(title="PulseBoard API")
r = get_redis()


# Endpoint 1: Login - create a session

class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/auth/login")
def login(req: LoginRequest):
    user = verify_credentials(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid Credentials")

    token = generate_session_token()
    login_session_key = f"session:{token}"

    login_session_data = {
        "user_id":          user["id"],
        "username":         user["name"],
        "role":             "member",
        "device":           "web",
        "created_at":       str(time.time()),
        "last_seen":        str(time.time()),
        "request_count":    "0",
    }

    r.hset(login_session_key, mapping=login_session_data)

    r.expire(login_session_key, SESSION_TTL)

    return {
        "token": token,
        "user_id": user["id"],
        "message": "Login successuf"
    }


# Endpoint 2: Get current session info

@app.get("/auth/session")
def get_session_info(token: str):
    session = get_session(token)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session")

    session_key = f"session:{token}"
    ttl = r.ttl(session_key)

    return {**session, "ttl_remaining": ttl}


# Endpoint 3: Increment request count (partial field update)

@app.post("/auth/session/ping")
def ping_session(token: str):
    session = get_session(token)
    session_key = f"session:{token}"
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session")

    new_count = r.hincrby(session_key, "request_count", 1)
    r.hset(session_key, "last_session", str(time.time()))

    return {
        "status":       "alive",
        "request_count": new_count,
    }


# Endpoint 4: Fetch only specific fields (selective read)
# The whole point of hashes = don't pay for what you don't need

@app.get("/auth/session/identity")
def get_identity(token: str):
    session_key = f"session:{token}"

    fields = ["user_id", "username", "role"]
    values = r.hmget(session_key, fields)

    if not values[0]:
        raise HTTPException(status_code=401, detail="Invalid session")

    return dict(zip(fields, values))


# Endpoint 5: Logout - destroy session

@app.post("/auth/logout")
def logout(token: str):
    session_key = f"session:{token}"

    deleted = r.delete(session_key)

    if not deleted:
        raise HTTPException(status_code=401, detail="Session not found")

    return {"message": "Logged out successfully"}


CACHE_TTL = 60

# ----- Phase 3 ----------------------------------------------
LEADERBOARD_KEY = "leaderboard:global"


# ------ Startup: seed leaderboard from "DB" into redis ------
@app.on_event("startup")
def seed_leaderboard():
    mapping = dict(LEADERBOARD_SEED)
    r.zadd(LEADERBOARD_KEY, mapping)
    print(f"Leaderboard seeded with {len(mapping)} users")


# Endpoint 1: Get top-N leaderboard

@app.get("/leaderboard")
def get_leaderboard(top_n: int = 5):
    results = r.zrevrange(LEADERBOARD_KEY, 0, top_n - 1, withscores=True)

    return {
        "leaderboard": [
            {"rank": idx + 1, "user": member, "score": int(score)}
            for idx, (member, score) in enumerate(results)
        ]
    }


# Endpoint 2: Add points to a user (the "earn points" action)

@app.post("/leaderboard/{username}/add-points")
def add_points(username: str, points: int):
    new_score = r.zincrby(LEADERBOARD_KEY, points, username)

    rank = r.zrevrank(LEADERBOARD_KEY, username)

    return {
        "user":      username,
        "new_score": int(new_score),
        "rank":      rank + 1,
    }


# Endpoint 3: Get a specific user's rank and score
@app.get("/leaderboard/{username}/rank")
def get_user_rank(username: str):
    score = r.zscore(LEADERBOARD_KEY, username)
    rank = r.zrevrank(LEADERBOARD_KEY, username)

    if score is None:
        raise HTTPException(
            status_code=404,
            detail=f"{username} not on leaderboard")

    # Bonus: how many users are on the leaderboard total
    total = r.zcard(LEADERBOARD_KEY)

    return {
        "user":         username,
        "score":        int(score),
        "rank":         rank + 1,
        "total_users":  total,
    }


# Endpoint 4: Get users within a score range
@app.get("/leaderboard/range/scores")
def get_users_in_score_range(min_score: int = 1000, max_score: int = 2000):
    results = r.zrangebyscore(
        LEADERBOARD_KEY,
        min_score, max_score, withscores=True)

    return {
        "min_score": min_score,
        "max_score": max_score,
        "count":     len(results),
        "users": [
            {"user": member, "score": int(score)}
            for member, score in results
        ]
    }


# Endpoint 5: Remove a user from leaderboard
@app.delete("/leaderboard/{username}")
def remove_from_leaderboard(username: str):
    removed = r.zrem(LEADERBOARD_KEY, username)

    if not removed:
        raise HTTPException(status_code=404, detail=f"{username} not found")

    return {"removed": username}


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
