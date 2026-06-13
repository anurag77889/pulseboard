import time

USERS = {
    "u1": {"id": "u1", "name": "Anurag", "city": "Mumbai", "score": 1500},
    "u2": {"id": "u2", "name": "Priya",  "city": "Bengaluru", "score": 2200},
    "u3": {"id": "u3", "name": "Rohan",  "city": "Delhi", "score": 980},
}


ACTION_TYPES = {
    "liked_post",
    "commented",
    "shared_post",
    "followed_user",
    "bookmarked"
}

LEADERBOARD_SEED = [
    ("Anurag", 1500),
    ("Priya",  2200),
    ("Rohan",  980),
    ("Sneha",  3100),
    ("Dev",    750),
]


def validate_action(action_type: str) -> bool:
    return action_type in ACTION_TYPES


def get_user_from_db(user_id: str) -> dict | None:
    time.sleep(0.05)  # simulate 50ms DB latency
    return USERS.get(user_id)


def update_user_in_db(user_id: str, updates: dict) -> dict | None:
    if user_id not in USERS:
        return None
    USERS[user_id].update(updates)
    return USERS[user_id]
