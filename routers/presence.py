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

    # Add username to the online set
    added = r.sadd(ONLINE_SET_KEY, username)

    return {
        "user":             username,
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
