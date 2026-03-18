"""FastAPI routes: auth, users, conversations, analyze/upload, UI, health."""
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from comparison.comparator import compare_report_mpd
from models.ollama_client import ping as ollama_ping

from auth import create_token, verify_password, verify_token, COOKIE_NAME, hash_password
from db import db_session
from models_db import Conversation, Message, User
from extraction.extractors import extract_text

router = APIRouter()


def get_session(request: Request) -> str | None:
    """Return session token from cookie or None."""
    return request.cookies.get(COOKIE_NAME)


def get_current_user(request: Request) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    user_id = verify_token(token)
    if not user_id:
        return None
    with db_session() as db:
        return db.query(User).filter(User.id == user_id).first()


def require_user(request: Request) -> User:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


@router.get("/", response_class=HTMLResponse)
async def index(user: User | None = Depends(get_current_user)):
    """Redirect to /chat if logged in, else /login."""
    if user:
        return RedirectResponse(url="/chat", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(user: User | None = Depends(get_current_user)):
    """Serve login page; redirect to /chat if already logged in."""
    if user:
        return RedirectResponse(url="/chat", status_code=302)
    p = Path(__file__).resolve().parent.parent / "templates" / "login.html"
    return HTMLResponse(content=p.read_text())


@router.post("/login")
async def login_post(request: Request):
    """Check password, set cookie, redirect to /chat."""
    form = await request.form()
    username = (form.get("username", "") or "").strip()
    password = form.get("password", "") or ""
    with db_session() as db:
        user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return RedirectResponse(url="/login?error=auth", status_code=302)
    response = RedirectResponse(url="/chat", status_code=302)
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_token(user.id),
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


class UserOut(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str
    is_admin: bool


class CreateUserIn(BaseModel):
    username: str
    first_name: str
    last_name: str
    password: str
    is_admin: bool = False


class ConversationOut(BaseModel):
    id: int
    title: str


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str
    raw_json: str | None = None


class AnalyzeResponse(BaseModel):
    analysis: str
    discrepancies: list[str]
    driver: str
    recommendations: list[str]
    compliance_notes: str
    conversation_id: int
    message_id: int


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    user: User = Depends(require_user),
):
    """Upload a PDF/DOCX/XLSX/TXT and return extracted text (requires login)."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 25MB)")

    try:
        text = extract_text(file.filename or "", file.content_type, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e!s}")

    if not text.strip():
        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "text": "",
            "warning": "No text extracted. If this PDF is scanned/image-based, OCR is required.",
        }
    return {"filename": file.filename, "content_type": file.content_type, "text": text}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(require_user)):
    return UserOut(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        is_admin=user.is_admin,
    )


@router.post("/admin/users", response_model=UserOut)
async def admin_create_user(payload: CreateUserIn, _: User = Depends(require_admin)):
    with db_session() as db:
        existing = db.query(User).filter(User.username == payload.username).first()
        if existing:
            raise HTTPException(status_code=409, detail="Username already exists")
        u = User(
            username=payload.username.strip(),
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            password_hash=hash_password(payload.password),
            is_admin=bool(payload.is_admin),
        )
        db.add(u)
        db.flush()
        return UserOut(
            id=u.id,
            username=u.username,
            first_name=u.first_name,
            last_name=u.last_name,
            is_admin=u.is_admin,
        )


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(user: User = Depends(require_user)):
    with db_session() as db:
        q = db.query(Conversation).order_by(Conversation.updated_at.desc())
        if not user.is_admin:
            q = q.filter(Conversation.user_id == user.id)
        return [ConversationOut(id=c.id, title=c.title) for c in q.limit(200).all()]


@router.post("/conversations", response_model=ConversationOut)
async def create_conversation(user: User = Depends(require_user)):
    with db_session() as db:
        c = Conversation(user_id=user.id, title="New conversation")
        db.add(c)
        db.flush()
        return ConversationOut(id=c.id, title=c.title)


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: int, user: User = Depends(require_user)):
    with db_session() as db:
        c = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if (not user.is_admin) and c.user_id != user.id:
            raise HTTPException(status_code=403, detail="Forbidden")
        db.delete(c)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def get_messages(conversation_id: int, user: User = Depends(require_user)):
    with db_session() as db:
        c = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if (not user.is_admin) and c.user_id != user.id:
            raise HTTPException(status_code=403, detail="Forbidden")
        msgs = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).all()
        return [
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                raw_json=m.raw_json,
                created_at=m.created_at.isoformat(),
            )
            for m in msgs
        ]


@router.post("/conversations/{conversation_id}/analyze", response_model=AnalyzeResponse)
async def analyze_conversation(
    conversation_id: int,
    request: Request,
    report_text: str = Form(""),
    mpd_context: str = Form(""),
    file: UploadFile | None = File(default=None),
    user: User = Depends(require_user),
):
    """Analyze text or uploaded file, store messages, return structured analysis."""
    with db_session() as db:
        c = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if (not user.is_admin) and c.user_id != user.id:
            raise HTTPException(status_code=403, detail="Forbidden")

        instruction = (report_text or "").strip()
        file_text = ""
        if file is not None and file.filename:
            data = await file.read()
            if data:
                try:
                    file_text = extract_text(file.filename or "", file.content_type, data).strip()
                except Exception as e:
                    raise HTTPException(status_code=400, detail=f"Could not read file: {e}")

        if instruction and file_text:
            text = f"{instruction}\n\n--- Attached: {file.filename} ---\n{file_text}"
        elif file_text:
            text = f"--- Attached: {file.filename} ---\n{file_text}"
        else:
            text = instruction

        if not text:
            raise HTTPException(status_code=400, detail="No report text or file provided")

        user_msg = Message(conversation_id=conversation_id, role="user", content=text)
        db.add(user_msg)
        db.flush()

        # Set title from first message if still default
        if c.title == "New conversation":
            title = " ".join(text.split()[:8]).strip()
            c.title = title[:200] if title else "New conversation"

        mpd = (mpd_context or "").strip() or "No MPD context provided."
    try:
        result = await compare_report_mpd(text, mpd)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama/perkins-ai error: {e!s}")

    raw_json = None
    try:
        import json

        raw_json = json.dumps(result, ensure_ascii=False)
    except Exception:
        raw_json = None

    with db_session() as db:
        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=result.get("analysis", ""),
            raw_json=raw_json,
        )
        db.add(assistant_msg)
        # bump updated_at
        c = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if c:
            from datetime import datetime

            c.updated_at = datetime.utcnow()
        db.flush()
        return AnalyzeResponse(
            analysis=result.get("analysis", ""),
            discrepancies=result.get("discrepancies", []),
            driver=result.get("driver", ""),
            recommendations=result.get("recommendations", []),
            compliance_notes=result.get("compliance_notes", ""),
            conversation_id=conversation_id,
            message_id=assistant_msg.id,
        )


@router.get("/chat", response_class=HTMLResponse)
async def chat(request: Request):
    """Serve chat UI (requires login); redirects to /login if unauthenticated."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    p = Path(__file__).resolve().parent.parent / "templates" / "chat.html"
    return HTMLResponse(content=p.read_text())


@router.get("/ping")
async def ping():
    """Health check; no auth required."""
    ok = ollama_ping()
    return {"status": "ok", "ollama": ok}
