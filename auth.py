"""Simple signed-cookie auth for Perkins."""
import os
from itsdangerous import URLSafeTimedSerializer, BadSignature

COOKIE_NAME = "perkins_session"
MAX_AGE = 60 * 60 * 24 * 7  # 7 days

_secret = os.environ.get("PERKINS_SECRET", "change-me-in-production")
_password = os.environ.get("PERKINS_PASSWORD", "perkins")
_serializer = URLSafeTimedSerializer(_secret, salt="perkins-login")


def verify_password(password: str) -> bool:
    return password == _password


def create_token() -> str:
    return _serializer.dumps("ok")


def verify_token(token: str) -> bool:
    try:
        _serializer.loads(token, max_age=MAX_AGE)
        return True
    except BadSignature:
        return False
