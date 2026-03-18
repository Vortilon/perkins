"""FastAPI routes: /, /login, /analyze, /chat, /ping."""
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from comparison.comparator import compare_report_mpd
from models.ollama_client import ping as ollama_ping

from auth import verify_password, create_token, verify_token, COOKIE_NAME

router = APIRouter()


def get_session(request: Request) -> str | None:
    """Return session token from cookie or None."""
    return request.cookies.get(COOKIE_NAME)


def is_authenticated(token: str | None = Depends(get_session)) -> bool:
    """True if valid session cookie."""
    return bool(token and verify_token(token))


@router.get("/", response_class=HTMLResponse)
async def index(token: str | None = Depends(get_session)):
    """Redirect to /chat if logged in, else /login."""
    if token and verify_token(token):
        return RedirectResponse(url="/chat", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(token: str | None = Depends(get_session)):
    """Serve login page; redirect to /chat if already logged in."""
    if token and verify_token(token):
        return RedirectResponse(url="/chat", status_code=302)
    p = Path(__file__).resolve().parent.parent / "templates" / "login.html"
    return HTMLResponse(content=p.read_text())


@router.post("/login")
async def login_post(request: Request):
    """Check password, set cookie, redirect to /chat."""
    form = await request.form()
    password = form.get("password", "")
    if not verify_password(password):
        return RedirectResponse(url="/login?error=auth", status_code=302)
    response = RedirectResponse(url="/chat", status_code=302)
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_token(),
        max_age=60 * 60 * 24 * 7,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout")
async def logout():
    """Clear session cookie and redirect to login."""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


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
async def analyze(
    req: AnalyzeRequest,
    auth: bool = Depends(is_authenticated),
):
    """Compare report text vs MPD context; return structured analysis."""
    if not auth:
        raise HTTPException(status_code=401, detail="Not authenticated")
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
async def chat(auth: bool = Depends(is_authenticated)):
    """Serve chat UI (requires login)."""
    if not auth:
        return RedirectResponse(url="/login", status_code=302)
    p = Path(__file__).resolve().parent.parent / "templates" / "chat.html"
    return HTMLResponse(content=p.read_text())


@router.get("/ping")
async def ping():
    """Health check; no auth required."""
    ok = ollama_ping()
    return {"status": "ok", "ollama": ok}
