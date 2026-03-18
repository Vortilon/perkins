"""Ollama client wrapper for Perkins AI (perkins-ai model)."""
import httpx
from typing import Optional

OLLAMA_BASE = "http://127.0.0.1:11434"
MODEL = "perkins-ai"
TIMEOUT = 120.0


def analyze(
    report_text: str,
    mpd_context: str,
    *,
    timeout: float = TIMEOUT,
) -> str:
    """Call perkins-ai model with report + MPD context; return raw response text."""
    prompt = f"""Compare the following customer report excerpt against the MPD context. Output structured analysis: discrepancies, drivers/causes, recommendations, compliance notes.

Report excerpt:
{report_text}

MPD context:
{mpd_context}

Analysis:"""
    with httpx.Client(timeout=timeout) as client:
        r = client.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": MODEL, "prompt": prompt, "stream": False},
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()


async def analyze_async(
    report_text: str,
    mpd_context: str,
    *,
    timeout: float = TIMEOUT,
) -> str:
    """Async version for FastAPI."""
    prompt = f"""Compare the following customer report excerpt against the MPD context. Output structured analysis: discrepancies, drivers/causes, recommendations, compliance notes.

Report excerpt:
{report_text}

MPD context:
{mpd_context}

Analysis:"""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": MODEL, "prompt": prompt, "stream": False},
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()


def ping() -> bool:
    """Check if Ollama is reachable."""
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            return r.status_code == 200
    except Exception:
        return False
