"""Perkins AI – FastAPI app (analyze report vs MPD, chat UI, health)."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api.routes import router

app = FastAPI(title="Perkins AI", description="Report vs MPD analysis (Ollama perkins-ai)")
app.include_router(router, prefix="", tags=["perkins"])

# Optional: mount static if we add assets later
# app.mount("/static", StaticFiles(directory="static"), name="static")
