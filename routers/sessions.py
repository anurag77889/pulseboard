# Phase 4 imports
import json
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from redis_client import get_redis
from fake_db import verify_credentials, generate_session_token

router = APIRouter(prefix="/auth", tags=["Phase 4 - Sessions"])
r = get_redis()

SESSION_TTL = 1800


# Get session data (used by protected endpoints)
def get_session(token: str) -> dict | None:
    session_key = f"session:{token}"

    session_data = r.hgetall(session_key)

    if not session_data:
        return None

    r.expire(session_key, SESSION_TTL)

    return session_data


# Endpoint 1: Login - create a session

class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
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

@router.get("/session")
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

@router.post("/session/ping")
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

@router.get("/session/identity")
def get_identity(token: str):
    session_key = f"session:{token}"

    fields = ["user_id", "username", "role"]
    values = r.hmget(session_key, fields)

    if not values[0]:
        raise HTTPException(status_code=401, detail="Invalid session")

    return dict(zip(fields, values))


# Endpoint 5: Logout - destroy session

@router.post("/logout")
def logout(token: str):
    session_key = f"session:{token}"

    deleted = r.delete(session_key)

    if not deleted:
        raise HTTPException(status_code=401, detail="Session not found")

    return {"message": "Logged out successfully"}


# Endpoint 6: Debug - see all active sessions (learning tool)

@router.get("/sessions/debug")
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
