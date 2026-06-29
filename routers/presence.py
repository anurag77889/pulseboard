from fastapi import APIRouter, HTTPException
from redis_client import get_redis
from fake_db import FOLLOW_GRAPH, username_exists

router = APIRouter(tags=["Phase 5 - Presence"])
r = get_redis()

ONLINE_SET_KEY = "online:users"


def seed():
    """Called once on startup from main.py"""
    for username, following in FOLLOW_GRAPH.items():
        if following:
            r.sadd(f"follows: {username}", *following)

# ════════════════════════════════════════════════════════════
# PART 1 — ONLINE PRESENCE
# ════════════════════════════════════════════════════════════


# Endpoint 1: Mark user as online

@router.post("/presence/{username}/online")
def mark_online(username: str):
    if not username_exists:
        return HTTPException(status_code=404, detail="User not found")

    added = r.sadd(ONLINE_SET_KEY, username)

    return {
        "username":         username,
        "status":           "online",
        "already_online":   added == 0,
        "online_count":     r.scard(ONLINE_SET_KEY)  # scard = set cardinality
    }


# Endpoint 2: Mark user as offline

@router.post("/presence/{username}/offline")
def mark_offline(username: str):

    # Remove username from the online set
    removed = r.srem(ONLINE_SET_KEY, username)

    return {
        "user":                 username,
        "status":               "offline",
        "was_online":           removed == 1,
        "online_count":         r.scard(ONLINE_SET_KEY)
    }


# Endpoint 3: Check if a specific user is online

@router.get("/presence/{username}/status")
def check_online_status(username: str):

    # Check membership in 0(1) - this is Sets' killer feature
    is_online = r.ismember(ONLINE_SET_KEY, username)

    return {
        "user": username,
        "online": is_online
    }


# Endpoint 4: Get all online users

@router.get("/presence/online/all")
def get_all_online_users():

    # Fetch every member of the set
    online_users = r.smembers(ONLINE_SET_KEY)

    return {
        "count": len(online_users),
        "users": list(online_users)
    }
