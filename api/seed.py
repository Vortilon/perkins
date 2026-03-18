from __future__ import annotations

import os

from db import db_session
from models_db import User
from auth import hash_password


def ensure_admin_user() -> None:
    """
    Create an initial admin user if none exists.

    Env vars:
      PERKINS_ADMIN_USERNAME (default: admin)
      PERKINS_ADMIN_PASSWORD (default: admin)
      PERKINS_ADMIN_FIRST (default: Admin)
      PERKINS_ADMIN_LAST (default: User)
    """
    username = os.environ.get("PERKINS_ADMIN_USERNAME", "admin").strip()
    password = os.environ.get("PERKINS_ADMIN_PASSWORD", "admin")
    first = os.environ.get("PERKINS_ADMIN_FIRST", "Admin")
    last = os.environ.get("PERKINS_ADMIN_LAST", "User")

    with db_session() as db:
        any_admin = db.query(User).filter(User.is_admin == True).first()  # noqa: E712
        if any_admin:
            return
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            existing.is_admin = True
            return
        db.add(
            User(
                username=username,
                first_name=first,
                last_name=last,
                password_hash=hash_password(password),
                is_admin=True,
            )
        )

