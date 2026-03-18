"""FastAPI routes: /analyze, /chat, /ping."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pathlib import Path

from comparison.comparator import compare_report_mpd
from models.ollama_client import ping as ollama_ping

router = APIRouter()


class AnalyzeRequest(BaseModel):
    report_text: str
    mpd_context: str = ""


class AnalyzeResponse(BaseModel):
    analysis: str
    discrepancies: list[str]
    driver: str
    recommendations: list[str]
    compliance_notes: str


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    """Compare report text vs MPD context; return structured analysis."""
    mpd = req.mpd_context or "No MPD context provided."
    try:
        result = await compare_report_mpd(req.report_text, mpd)
        return AnalyzeResponse(
            analysis=result["analysis"],
            discrepancies=result.get("discrepancies", []),
            driver=result.get("driver", ""),
            recommendations=result.get("recommendations", []),
            compliance_notes=result.get("compliance_notes", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama/perkins-ai error: {e!s}")


@router.get("/chat", response_class=HTMLResponse)
async def chat():
    """Serve simple chat UI that POSTs to /analyze."""
    p = Path(__file__).resolve().parent.parent / "templates" / "chat.html"
    return HTMLResponse(content=p.read_text())


@router.get("/ping")
async def ping():
    """Health check; also checks Ollama availability."""
    ok = ollama_ping()
    return {"status": "ok", "ollama": ok}
