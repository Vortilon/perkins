"""Perkins AI – FastAPI app (analyze report vs MPD, chat UI, health)."""
import asyncio
import httpx
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api.routes import router
from db import engine
from models_db import Base
from api.seed import ensure_admin_user

log = logging.getLogger("perkins")

app = FastAPI(title="Perkins AI", description="Report vs MPD analysis (Ollama perkins-ai)")
app.include_router(router, prefix="", tags=["perkins"])

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


async def _warmup_model() -> None:
    """Send a minimal dummy request so Ollama loads perkins-ai into RAM on startup."""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            await client.post(
                "http://localhost:11434/api/generate",
                json={"model": "perkins-ai", "prompt": "ready", "stream": False},
            )
        log.info("perkins-ai model warmed up and loaded into RAM")
    except Exception as exc:
        log.warning("Model warm-up failed (will load on first query): %s", exc)


@app.on_event("startup")
def _startup():
    Base.metadata.create_all(bind=engine)
    ensure_admin_user()
    asyncio.create_task(_warmup_model())
