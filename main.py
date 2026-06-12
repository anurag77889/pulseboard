import json
from fastapi import FastAPI, HTTPException
from redis_client import get_redis
from fake_db import get_user_from_db, update_user_in_db


app = FastAPI(title="PulseBoard API")
