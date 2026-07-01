from fastapi import APIRouter, HTTPException
from redis_client import get_redis
from fake_db import FOLLOW_GRAPH, username_exists

router = APIRouter(tags=["Phase 5 - Presence"], prefix="/presence")
r = get_redis()

ONLINE_SET_KEY = "online:users"


def seed():
    """Called once on startup from main.py"""
    for username, following in FOLLOW_GRAPH.items():
        follows_key = f"follows:{username}"
        r.sadd(follows_key, *following)

# ════════════════════════════════════════════════════════════
# PART 1 — ONLINE PRESENCE
# ════════════════════════════════════════════════════════════


# Endpoint 1: Mark user as online

@router.post("/{username}/online")
def mark_online(username: str):
    if not username_exists:
        raise HTTPException(status_code=404, detail="User not found")

    added = r.sadd(ONLINE_SET_KEY, username)

    return {
        "username":         username,
        "status":           "online",
        "already_online":   added == 0,
        "online_count":     r.scard(ONLINE_SET_KEY)  # scard = set cardinality
    }


# Endpoint 2: Mark user as offline

@router.post("/{username}/offline")
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

@router.get("/{username}/status")
def check_online_status(username: str):

    # Check membership in 0(1) - this is Sets' killer feature
    is_online = r.sismember(ONLINE_SET_KEY, username)

    return {
        "user": username,
        "online": is_online
    }


# Endpoint 4: Get all online users

@router.get("/online/all")
def get_all_online_users():

    # Fetch every member of the set
    online_users = r.smembers(ONLINE_SET_KEY)

    return {
        "count": len(online_users),
        "users": list(online_users)
    }


# ════════════════════════════════════════════════════════════
# PART 2 — SOCIAL GRAPH
# ════════════════════════════════════════════════════════════

# Endpoint 5: Follow a user
@router.post("/users/{username}/follow/{target}")
def follow_user(username: str, target: str):
    if username == target:
        raise HTTPException(status_code=404, detail="Cannot follow yourself")
    if not username_exists(target):
        raise HTTPException(status_code=404, detail="Target user not found")

    follows_key = f"follows:{username}"

    # Add target to the username's follows set
    added = r.sadd(follows_key, target)

    return {
        "follower":             username,
        "following":            target,
        "already_followed":     added == 0,
        "total_following":      r.scard(follows_key)
    }


# Enpoint 6: Unfollow a user
@router.delete("/users/{username}/follow/{target}")
def unfollow_user(username: str, target: str):

    follows_key = f"follows:{username}"

    # Remove target from follows set
    removed = r.srem(follows_key, target)

    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"{username} wasn't following {target}"
        )

    return {
        "unfollowed":           target,
        "total_following":      r.scard(follows_key)
    }


# Endpoint 7: Get following list
@router.get("/users/{username}/following")
def get_following(username: str):

    follows_key = f"follows:{username}"

    following = r.smembers(follows_key)

    return {
        "user":         username,
        "count":        len(following),
        "following":    list(following)
    }


# Endpoint 8: Mutual Follows
# The SINTER showcase - one command, no loops, no SQL JOIN

@router.get("/users/{username}/mutuals/{other}")
def get_mutual_follows(username: str, other: str):

    # Find users that BOTH username and other follow
    mutuals = r.sinter(f"follows:{username}", f"follows:{other}")

    return {
        "between":      [username, other],
        "count":        len(mutuals),
        "mutuals":      list(mutuals),
    }


# Endpoint 9: Follow suggestions
# SDIFF: "who does `source` follow that `username` doesn't?"
# Real-world: LinkedIn "People you may know", Instagram "Suggested for you"

@router.get("/users/{username}/suggestions")
def get_follow_suggestions(username: str, based_on: str):
    """
    Returns users that `based_on` follows but `username` doesn't.
    e.g. /users/Anurag/suggestions?based_on=Priya
    → who Priya follows that Anurag doesn't (yet)
    """

    suggestions = r.sdiff(f"follows:{based_on}", f"follows:{username}")

    suggestions.discard(username)

    return {
        "for_user": username,
        "based_on": based_on,
        "count":    len(suggestions),
        "suggestions": list(suggestions)
    }
