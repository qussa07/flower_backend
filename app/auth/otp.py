import secrets
from hmac import compare_digest
from uuid import UUID, uuid4

from redis.exceptions import WatchError

from database import get_redis


CODE_TTL = 600
SEND_COOLDOWN = 60
MAX_ATTEMPTS = 5


def _session_key(registration_id: UUID) -> str:
    return f"otp:session:{registration_id}"


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def is_on_cooldown(email: str) -> bool:
    return bool(get_redis().exists(f"otp:cooldown:{email.lower()}"))



def issue_code(email: str, code: str) -> tuple[UUID, str] | None:
    email = email.lower()
    cooldown_key = f"otp:cooldown:{email}"
    registration_id = uuid4()
    session_key = _session_key(registration_id)

    while True:
        with get_redis().pipeline() as pipe:
            try:
                pipe.watch(cooldown_key)
                if pipe.exists(cooldown_key):
                    return None

                pipe.multi()
                pipe.hset(session_key, mapping={
                    "email": email,
                    "code": code,
                    "attempts": 0,
                })
                pipe.expire(session_key, CODE_TTL)
                pipe.set(cooldown_key, "1", ex=SEND_COOLDOWN)
                pipe.execute()
                return registration_id, code
            except WatchError:
                continue


def check_code(registration_id: UUID, code: str) -> str | None:
    session_key = _session_key(registration_id)

    while True:
        with get_redis().pipeline() as pipe:
            try:
                pipe.watch(session_key)
                record = pipe.hgetall(session_key)
                if not record:
                    return None

                if compare_digest(record["code"], code):
                    return record["email"]

                pipe.multi()
                if int(record["attempts"]) + 1 >= MAX_ATTEMPTS:
                    pipe.delete(session_key)
                else:
                    pipe.hincrby(session_key, "attempts", 1)
                pipe.execute()
                return None
            except WatchError:
                continue


def delete_code(registration_id: UUID) -> None:
    get_redis().delete(_session_key(registration_id))