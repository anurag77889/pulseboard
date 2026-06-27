# Phase 3 imports
from fastapi import APIRouter, HTTPException
from redis_client import get_redis
from fake_db import LEADERBOARD_SEED

router = APIRouter(prefix="/leaderboard", tags=["Phase 3 - Leaderboard"])
r = get_redis()

# ----- Phase 3 ----------------------------------------------
LEADERBOARD_KEY = "leaderboard:global"


def seed():
    """Called once on startup from main.py"""
    r.zadd(LEADERBOARD_KEY,
           {member: score for member, score in LEADERBOARD_SEED})


# Endpoint 1: Get top-N leaderboard

@router.get("/leaderboard")
def get_leaderboard(top_n: int = 5):
    results = r.zrevrange(LEADERBOARD_KEY, 0, top_n - 1, withscores=True)

    return {
        "leaderboard": [
            {"rank": idx + 1, "user": member, "score": int(score)}
            for idx, (member, score) in enumerate(results)
        ]
    }


# Endpoint 2: Add points to a user (the "earn points" action)

@router.post("/leaderboard/{username}/add-points")
def add_points(username: str, points: int):
    new_score = r.zincrby(LEADERBOARD_KEY, points, username)

    rank = r.zrevrank(LEADERBOARD_KEY, username)

    return {
        "user":      username,
        "new_score": int(new_score),
        "rank":      rank + 1,
    }


# Endpoint 3: Get a specific user's rank and score
@router.get("/leaderboard/{username}/rank")
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
@router.get("/leaderboard/range/scores")
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
@router.delete("/leaderboard/{username}")
def remove_from_leaderboard(username: str):
    removed = r.zrem(LEADERBOARD_KEY, username)

    if not removed:
        raise HTTPException(status_code=404, detail=f"{username} not found")

    return {"removed": username}

