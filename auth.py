"""Per-user auth: signed cookie with user_id."""
from __future__ import annotations

import os
from dataclasses import dataclass

import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature

COOKIE_NAME = "perkins_session"
MAX_AGE = 60 * 60 * 24 * 7  # 7 days

_secret = os.environ.get("PERKINS_SECRET", "change-me-in-production")
_serializer = URLSafeTimedSerializer(_secret, salt="perkins-login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


def create_token(user_id: int) -> str:
    return _serializer.dumps({"user_id": user_id})


def verify_token(token: str) -> int | None:
    """Return user_id if token valid, else None."""
    try:
        data = _serializer.loads(token, max_age=MAX_AGE)
        uid = data.get("user_id")
        return int(uid) if uid is not None else None
    except (BadSignature, Exception):
        return None
