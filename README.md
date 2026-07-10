# PulseBoard

A small FastAPI backend built to learn **Redis end-to-end** — not just "what is Redis," but how each of its core data structures solves a real production problem.

---

## Why this project exists

Most Redis tutorials show you `SET` and `GET` and call it a day. That's maybe 10% of what Redis is actually used for in production.

PulseBoard simulates a small social platform — and every feature was picked because it's a textbook real-world use case for a specific Redis data structure:

| Feature | Redis Data Structure | What it teaches |
|---|---|---|
| User profile caching | **String** | Cache-aside pattern, TTL, invalidation |
| Activity feed | **List** | Ordered, bounded, append-heavy data |
| Leaderboard | **Sorted Set** | Atomic ranking, score-based queries |
| Login sessions | **Hash** | Structured objects, partial field updates |
| Online presence & social graph | **Set** | Membership checks, intersection/difference |
| API rate limiting & live notifications | **String + Pub/Sub** | Atomic counters, real-time broadcasting |

By the time you've played with all six, you'll understand *why* Redis is used the way it is in real backends — not just the commands.

---

## What you'll need

- Python 3.10+
- Redis running locally
- `curl` or Postman/Swagger UI for testing
- ~30–60 minutes if you want to walk through every feature

---

## Quick start

### 1. Get Redis running

**macOS:**
```bash
brew install redis
brew services start redis
```

**Ubuntu / Debian:**
```bash
sudo apt update && sudo apt install redis-server
sudo systemctl start redis-server
```

**Windows:** use [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) and follow the Ubuntu steps above, or run Redis via Docker:
```bash
docker run -d -p 6379:6379 redis:latest
```

**Verify it's running:**
```bash
redis-cli ping
```
You should see `PONG`. If you don't, Redis isn't running — check the steps above before continuing.

### 2. Clone and set up the project

```bash
git clone https://github.com/anurag77889/pulseboard.git
cd pulseboard

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Run it

```bash
uvicorn main:app --reload
```

The API is now live at **http://localhost:8000**.

Open **http://localhost:8000/docs** — that's FastAPI's built-in Swagger UI. You can try every single endpoint from your browser without writing any `curl` commands. This is the easiest way to explore the project.

---

## Project structure

```
pulseboard/
├── main.py                 # App entry point — wires everything together
├── redis_client.py         # Single shared Redis connection
├── fake_db.py               # In-memory "database" (no real DB needed)
├── requirements.txt
└── routers/
    ├── cache.py             # Feature 1 — Strings
    ├── feed.py               # Feature 2 — Lists
    ├── leaderboard.py        # Feature 3 — Sorted Sets
    ├── sessions.py            # Feature 4 — Hashes
    ├── presence.py            # Feature 5 — Sets
    ├── rate_limiter.py        # Feature 6a — Strings (rate limiting)
    └── notifications.py       # Feature 6b — Pub/Sub
```

Each file in `routers/` is self-contained — one feature, one Redis data structure, one thing to understand at a time. There's no real database; `fake_db.py` is a plain Python dict standing in for one, so 100% of the focus stays on Redis.

---

## Walkthrough — try every feature

Each section below is copy-paste runnable. Open a terminal and go in order, or jump to whichever feature interests you most.

### 1. Caching (Strings)

```bash
# First call — slow, hits the "database"
curl http://localhost:8000/users/u1

# Second call — instant, served from Redis cache
curl http://localhost:8000/users/u1

# Peek at the cache directly
curl http://localhost:8000/cache/inspect/u1
```
Look for `"source": "db"` on the first call and `"source": "cache"` on the second.

---

### 2. Activity feed (Lists)

```bash
# Record some actions
curl -X POST http://localhost:8000/users/u1/actions \
  -H "Content-Type: application/json" \
  -d '{"action_type": "liked_post", "target_id": "post_42"}'

# Read the feed back — most recent first
curl http://localhost:8000/users/u1/feed
```

---

### 3. Leaderboard (Sorted Sets)

```bash
# See the top 5 right now
curl http://localhost:8000/leaderboard

# Give someone points and watch their rank update
curl -X POST "http://localhost:8000/leaderboard/Rohan/add-points?points=500"

curl http://localhost:8000/leaderboard
```

---

### 4. Login sessions (Hashes)

```bash
# Log in — get a session token back
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "Anurag", "password": "password123"}'

# Copy the token from the response, then:
export TOKEN="paste_token_here"

curl "http://localhost:8000/auth/session?token=$TOKEN"
```

---

### 5. Presence & social graph (Sets)

```bash
curl -X POST http://localhost:8000/presence/Anurag/online
curl -X POST http://localhost:8000/presence/Priya/online

curl http://localhost:8000/presence/online/all

# Who do Anurag and Priya both follow?
curl http://localhost:8000/users/Anurag/mutuals/Priya
```

---

### 6a. Rate limiting (Strings + atomic counters)

```bash
# Hit this 6 times fast — the 6th request gets blocked
for i in 1 2 3 4 5 6; do
  curl -s "http://localhost:8000/api/protected-resource?username=Anurag"
  echo ""
done
```

---

### 6b. Live notifications (Pub/Sub)

This one needs **two terminals**, since you need a listener and a sender running at the same time.

**Terminal A** — connect a listener (requires [`websocat`](https://github.com/vi/websocat), or use a browser console):
```bash
websocat ws://localhost:8000/ws/notifications/Anurag
```

**Terminal B** — send a notification while Terminal A is still open:
```bash
curl -X POST http://localhost:8000/users/Anurag/notify \
  -H "Content-Type: application/json" \
  -d '{"message": "Priya liked your post"}'
```

The message should appear instantly in Terminal A.

---

## See what Redis is actually doing

This is the most underrated way to build real intuition. Open `redis-cli` in a separate terminal:

```bash
redis-cli

> KEYS *                    # every key currently in Redis
> TYPE user:u1               # see the data type behind any key
> MONITOR                    # streams every command Redis receives, live
```

Run `MONITOR`, then hit a few endpoints from another terminal or from `/docs`. You'll watch the exact Redis commands fire in real time — it's the fastest way to connect "I called this API" to "this is what happened in Redis."

---

## Common issues

**`redis.exceptions.ConnectionError`**
Redis isn't running. Run `redis-cli ping` — if it doesn't return `PONG`, start Redis using the steps in Quick Start.

**Port 8000 already in use**
Run on a different port: `uvicorn main:app --reload --port 8001`

**WebSocket notification not arriving**
Pub/Sub is fire-and-forget — the subscriber (Terminal A) must already be connected *before* you publish. If you publish first, the message is lost; there's nothing to replay it. This is intentional and a good thing to notice — it's a real limitation of Redis Pub/Sub.

---

## What's intentionally left out

This project skips a few things on purpose, to keep the focus on core Redis mechanics:

- **No real database** — `fake_db.py` is a Python dict. Adding Postgres would split focus away from Redis.
- **No authentication hardening** — passwords are stored in plaintext in `fake_db.py` for simplicity. Don't reuse this auth pattern anywhere real.
- **No Redis Cluster / persistence config** — this runs against a single local Redis instance with defaults. Production Redis setups (replication, RDB/AOF persistence, Sentinel/Cluster) are a separate, deeper topic.

If you want to go further after this, natural next steps are: connection pooling, Redis Streams (durable Pub/Sub), and Redis Cluster for horizontal scaling.

---

## License

MIT — use this however you like, for learning or for forking into your own project.
