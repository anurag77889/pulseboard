from fastapi import FastAPI
from routers import cache, feed, leaderboard, sessions, presence

app = FastAPI(title="Pulseboard API")

# ─── Startup: seed data that needs Redis to be ready ──────
# Seed functions live in their router files but are called from one place here.
# This keeps startup logic centralized and easy to find.


@app.on_event("startup")
def on_startup():
    leaderboard.seed()
    presence.seed()


# ─── Mount all routers ────────────────────────────

app.include_router(cache.router)
app.include_router(feed.router)
app.include_router(leaderboard.router)
app.include_router(sessions.router)
app.include_router(presence.router)
