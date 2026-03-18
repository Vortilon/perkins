from __future__ import annotations

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker, DeclarativeBase


class Base(DeclarativeBase):
    pass


def _db_url() -> str:
    # Default for VPS; can override with PERKINS_DB_URL
    return os.environ.get("PERKINS_DB_URL", "sqlite:////root/perkins/perkins.db")


engine = create_engine(
    _db_url(),
    connect_args={"check_same_thread": False} if _db_url().startswith("sqlite:") else {},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Session:
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


@contextmanager
def db_session() -> Session:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

