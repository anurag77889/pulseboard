import redis

# redis.Redis() connects to localhost:6379 by default
# decode_responses=True means all returned values are str, not bytes
r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)


def get_redis():
    return r
