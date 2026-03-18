"""Per-user auth: signed cookie with user_id."""
from __future__ import annotations

import os
from dataclasses import dataclass

from itsdangerous import URLSafeTimedSerializer, BadSignature
from passlib.context import CryptContext

COOKIE_NAME = "perkins_session"
MAX_AGE = 60 * 60 * 24 * 7  # 7 days

_secret = os.environ.get("PERKINS_SECRET", "change-me-in-production")
_serializer = URLSafeTimedSerializer(_secret, salt="perkins-login")
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd.verify(password, password_hash)


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
