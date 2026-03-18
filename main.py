"""Perkins AI – FastAPI app (analyze report vs MPD, chat UI, health)."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api.routes import router
from db import engine
from models_db import Base
from api.seed import ensure_admin_user

app = FastAPI(title="Perkins AI", description="Report vs MPD analysis (Ollama perkins-ai)")
app.include_router(router, prefix="", tags=["perkins"])

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
def _startup():
    Base.metadata.create_all(bind=engine)
    ensure_admin_user()
