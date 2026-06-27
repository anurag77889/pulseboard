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


# Endpoint 6: Debug - see all active sessions (learning tool)

@app.get("/auth/sessions/debug")
def list_all_sessions():
    session_keys = r.keys("session:*")

    sessions = []

    for key in session_keys:
        values = r.hmget(
            session_keys,
            ["username", "request_count", "last_seen"])
        sessions.append({
            "key":              key,
            "username":         values[0],
            "request_count":    values[1],
            "ttl":              r.ttl(session_keys),
        })

    return {
        "active_sessions": len(sessions),
        "sessions": sessions
    }


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
