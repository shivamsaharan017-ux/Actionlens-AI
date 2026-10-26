from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import re
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import Base, engine, get_db, SessionLocal
from app.models import ChecklistItem, Conversation, Notice, Preference, ProcessingLog, Reminder, User
from app.schemas import AnalyzeInput, ChecklistItemOut, ChecklistPatch, LoginInput, NoticeOut, PreferenceInput, QuestionInput, ReminderCreate, ReminderPatch, TranslateInput, UserCreate, UserOut
from app.services.ai import analyze_notice, answer_question, translate_text
from app.services.extraction import extract_file
from app.services.security import admin_user, current_user, hash_password, make_token, verify_password


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        for email, name, password, role in [
            ("demo@actionlens.ai", "Demo Citizen", "ActionLens2026!", "citizen"),
            ("admin@actionlens.ai", "Demo Administrator", "ActionLensAdmin2026!", "admin"),
        ]:
            if not db.query(User).filter_by(email=email).first():
                user = User(name=name, email=email, password_hash=hash_password(password), role=role)
                db.add(user)
                db.flush()
                db.add(Preference(user_id=user.id))
        db.commit()
    finally:
        db.close()
    yield


app = FastAPI(title="ActionLens AI API", version="1.0.0", description="Accessible notice analysis and action planning API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def _owned_notice(db: Session, notice_id: int, user: User) -> Notice:
    notice = db.query(Notice).filter(Notice.id == notice_id, Notice.user_id == user.id).first()
    if not notice:
        raise HTTPException(404, "Notice not found.")
    return notice


def _notice_response(notice: Notice) -> dict:
    return {"id": notice.id, "title": notice.title, "filename": notice.filename, "category": notice.category, "status": notice.status, "source_language": notice.source_language, "target_language": notice.target_language, "demo_mode": notice.demo_mode, "created_at": notice.created_at, "source_text": notice.source_text, "analysis": notice.analysis, "checklist": [{"id": item.id, "text": item.text, "due_date": item.due_date, "completed": item.completed, "position": item.position} for item in sorted(notice.checklist, key=lambda item: item.position)], "messages": [{"role": message.role, "content": message.content, "created_at": message.created_at} for message in notice.messages]}


def _reminder_response(reminder: Reminder, notice_title: str | None = None) -> dict:
    return {"id": reminder.id, "title": reminder.title, "reminder_date": reminder.reminder_date, "due_date": reminder.due_date, "enabled": reminder.enabled, "notice_id": reminder.notice_id, "notice_title": notice_title, "created_at": reminder.created_at}


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "live" if settings.ai_base_url and settings.ai_api_key else "demo", "model": settings.ai_model}


@app.post("/api/auth/register")
def register(payload: UserCreate, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "An account with this email already exists.")
    if payload.role not in {"citizen", "institution"}:
        raise HTTPException(422, "Choose Citizen or Institution.")
    user = User(name=payload.name.strip(), email=email, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    db.flush()
    db.add(Preference(user_id=user.id))
    db.commit()
    db.refresh(user)
    return {"access_token": make_token(user.id), "token_type": "bearer", "user": UserOut.model_validate(user)}


@app.post("/api/auth/login")
def login(payload: LoginInput, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect.")
    return {"access_token": make_token(user.id), "token_type": "bearer", "user": UserOut.model_validate(user)}


@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@app.post("/api/notices/upload")
async def upload_notice(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    allowed = {"application/pdf", "text/plain", "text/markdown", "text/csv", "image/png", "image/jpeg", "image/webp"}
    suffix = Path(file.filename or "").suffix.lower()
    allowed_suffix = {".pdf", ".txt", ".md", ".csv", ".png", ".jpg", ".jpeg", ".webp"}
    if file.content_type not in allowed and suffix not in allowed_suffix:
        raise HTTPException(415, "Use a PDF, image, or plain-text file.")
    body = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(body) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds the {settings.max_upload_mb} MB limit.")
    safe_name = Path(file.filename or "notice").name[:200]
    stored_path = Path(settings.storage_dir) / f"{uuid4().hex}{suffix}"
    stored_path.write_bytes(body)
    try:
        text = extract_file(str(stored_path), file.content_type or "")
    except Exception as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(422, f"Could not read this file: {exc}")
    if not text.strip():
        stored_path.unlink(missing_ok=True)
        raise HTTPException(422, "No readable text was found. Try a clearer scan or paste the notice text instead.")
    title = next((line.strip() for line in text.splitlines() if line.strip()), safe_name)[:255]
    notice = Notice(user_id=user.id, title=title, filename=safe_name, storage_path=str(stored_path), source_text=text, status="ready")
    db.add(notice)
    db.flush()
    db.add(ProcessingLog(notice_id=notice.id, user_id=user.id, event="extracted", detail=f"Extracted {len(text)} characters"))
    db.commit()
    db.refresh(notice)
    return {"notice": _notice_response(notice), "extracted_characters": len(text), "ocr_review": file.content_type.startswith("image/") or (file.content_type == "application/pdf" and not bool(text.strip()))}


@app.post("/api/notices/analyze")
async def analyze(payload: AnalyzeInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if payload.notice_id:
        notice = _owned_notice(db, payload.notice_id, user)
    elif payload.text and payload.text.strip():
        text = payload.text.strip()
        title = next((line.strip() for line in text.splitlines() if line.strip()), "Pasted notice")[:255]
        notice = Notice(user_id=user.id, title=title, source_text=text, status="processing")
        db.add(notice)
        db.commit()
        db.refresh(notice)
    else:
        raise HTTPException(422, "Upload a notice or paste its text to continue.")
    if not notice.source_text.strip():
        raise HTTPException(422, "This notice has no extracted text to analyze.")
    notice.status = "processing"
    db.commit()
    try:
        result = await analyze_notice(notice.source_text, payload.language, payload.reading_level)
        notice.analysis = result
        notice.title = (result.get("notice_title") or notice.title)[:255]
        notice.target_language = payload.language
        notice.demo_mode = bool(result.get("demo_mode"))
        notice.category = "Scholarship" if re.search(r"scholarship|grant", notice.source_text, re.I) else "Education" if re.search(r"college|university|admission", notice.source_text, re.I) else "General"
        notice.status = "completed" if not result.get("uncertain_information") else "needs_review"
        for old in list(notice.checklist):
            db.delete(old)
        for index, item in enumerate(result.get("checklist", [])):
            if isinstance(item, str):
                item = {"text": item}
            if item.get("text"):
                db.add(ChecklistItem(notice_id=notice.id, text=str(item["text"]), due_date=item.get("due_date"), position=index))
        db.add(ProcessingLog(notice_id=notice.id, user_id=user.id, event="analyzed", detail="Demo mode" if notice.demo_mode else f"Model: {settings.ai_model}"))
        db.commit()
        db.refresh(notice)
    except Exception as exc:
        notice.status = "failed"
        db.add(ProcessingLog(notice_id=notice.id, user_id=user.id, event="failed", detail=str(exc)[:500]))
        db.commit()
        raise HTTPException(502, "Analysis could not be completed. Check the provider settings and try again.")
    return {"notice": _notice_response(notice), "analysis": result, "mode": "demo" if notice.demo_mode else "live"}


@app.get("/api/notices")
def list_notices(search: str = "", status: str = "", category: str = "", language: str = "", date_from: str = "", date_to: str = "", sort: str = "newest", page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = db.query(Notice).filter(Notice.user_id == user.id)
    if search:
        query = query.filter(Notice.title.ilike(f"%{search}%"))
    if status:
        query = query.filter(Notice.status == status)
    if category:
        query = query.filter(Notice.category == category)
    if language:
        query = query.filter(Notice.target_language == language)
    try:
        if date_from:
            query = query.filter(Notice.created_at >= datetime.combine(date.fromisoformat(date_from), datetime.min.time()))
        if date_to:
            query = query.filter(Notice.created_at < datetime.combine(date.fromisoformat(date_to) + timedelta(days=1), datetime.min.time()))
    except ValueError:
        raise HTTPException(422, "Use valid dates in YYYY-MM-DD format.")
    total = query.count()
    query = query.order_by(Notice.created_at.asc() if sort == "oldest" else Notice.title.asc() if sort == "title" else Notice.created_at.desc())
    rows = query.offset((page - 1) * limit).limit(limit).all()
    return {"items": [NoticeOut.model_validate(row) for row in rows], "total": total, "page": page, "limit": limit}


@app.get("/api/notices/{notice_id}")
def get_notice(notice_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _notice_response(_owned_notice(db, notice_id, user))


@app.delete("/api/notices/{notice_id}")
def delete_notice(notice_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    notice = _owned_notice(db, notice_id, user)
    if notice.storage_path:
        Path(notice.storage_path).unlink(missing_ok=True)
    db.query(Reminder).filter(Reminder.notice_id == notice_id, Reminder.user_id == user.id).update({Reminder.notice_id: None})
    db.delete(notice)
    db.commit()
    return {"deleted": True, "id": notice_id}


@app.get("/api/notices/{notice_id}/checklist", response_model=list[ChecklistItemOut])
def get_checklist(notice_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    notice = _owned_notice(db, notice_id, user)
    return sorted(notice.checklist, key=lambda item: item.position)


@app.patch("/api/checklists/{checklist_id}/items/{item_id}")
def patch_checklist(checklist_id: int, item_id: int, payload: ChecklistPatch, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.query(ChecklistItem).join(Notice).filter(ChecklistItem.id == item_id, Notice.id == checklist_id, Notice.user_id == user.id).first()
    if item is None:
        raise HTTPException(404, "Checklist item not found.")
    item.completed = payload.completed
    db.commit()
    db.refresh(item)
    return ChecklistItemOut.model_validate(item)


@app.get("/api/reminders")
def list_reminders(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Reminder, Notice.title).outerjoin(Notice, Reminder.notice_id == Notice.id).filter(Reminder.user_id == user.id).order_by(Reminder.enabled.desc(), Reminder.reminder_date.asc(), Reminder.id.desc()).all()
    return {"items": [_reminder_response(reminder, notice_title) for reminder, notice_title in rows]}


@app.post("/api/reminders")
def create_reminder(payload: ReminderCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    title = payload.title.strip()
    if not title:
        raise HTTPException(422, "Add a short reminder description.")
    if payload.notice_id is not None:
        _owned_notice(db, payload.notice_id, user)
    reminder = Reminder(user_id=user.id, notice_id=payload.notice_id, title=title, reminder_date=payload.reminder_date, due_date=payload.due_date, enabled=True)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    notice_title = db.query(Notice.title).filter(Notice.id == reminder.notice_id, Notice.user_id == user.id).scalar() if reminder.notice_id else None
    return _reminder_response(reminder, notice_title)


@app.patch("/api/reminders/{reminder_id}")
def update_reminder(reminder_id: int, payload: ReminderPatch, db: Session = Depends(get_db), user: User = Depends(current_user)):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == user.id).first()
    if reminder is None:
        raise HTTPException(404, "Reminder not found.")
    reminder.enabled = payload.enabled
    db.commit()
    db.refresh(reminder)
    notice_title = db.query(Notice.title).filter(Notice.id == reminder.notice_id, Notice.user_id == user.id).scalar() if reminder.notice_id else None
    return _reminder_response(reminder, notice_title)


@app.delete("/api/reminders/{reminder_id}")
def delete_reminder(reminder_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == user.id).first()
    if reminder is None:
        raise HTTPException(404, "Reminder not found.")
    db.delete(reminder)
    db.commit()
    return {"deleted": True, "id": reminder_id}


@app.post("/api/notices/{notice_id}/questions")
async def ask_question(notice_id: int, payload: QuestionInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    notice = _owned_notice(db, notice_id, user)
    db.add(Conversation(notice_id=notice_id, role="user", content=payload.question))
    try:
        answer = await answer_question(notice.source_text, payload.question)
    except Exception:
        raise HTTPException(502, "The assistant is temporarily unavailable. Please try again.")
    db.add(Conversation(notice_id=notice_id, role="assistant", content=answer))
    db.commit()
    return {"answer": answer, "grounded_in": notice.title, "demo_mode": notice.demo_mode}


@app.post("/api/notices/{notice_id}/translate")
async def translate_notice(notice_id: int, payload: TranslateInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    notice = _owned_notice(db, notice_id, user)
    if not notice.analysis:
        raise HTTPException(409, "Analyze this notice before translating it.")
    try:
        translated = await translate_text(notice.analysis.get("plain_language_summary", ""), payload.language)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    except Exception:
        raise HTTPException(502, "Translation could not be completed. Please try again.")
    notice.analysis = {**notice.analysis, "translated_summary": translated}
    notice.target_language = payload.language
    db.commit()
    return {"language": payload.language, "translated_summary": translated}


@app.get("/api/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db), user: User = Depends(current_user)):
    notices = db.query(Notice).filter(Notice.user_id == user.id).all()
    checklist_items = db.query(ChecklistItem).join(Notice).filter(Notice.user_id == user.id).all()
    month_names = [(datetime.now(timezone.utc).replace(day=1) - timedelta(days=30 * offset)).strftime("%b") for offset in reversed(range(6))]
    activity = []
    for month in month_names:
        count = sum(1 for notice in notices if notice.created_at and notice.created_at.strftime("%b") == month)
        activity.append({"month": month, "notices": count})
    active_reminders = db.query(func.count(Reminder.id)).filter(Reminder.user_id == user.id, Reminder.enabled.is_(True)).scalar() or 0
    return {"total_notices": len(notices), "successfully_analyzed": sum(n.status in {"completed", "needs_review"} for n in notices), "pending_actions": sum(not item.completed for item in checklist_items), "saved_documents": sum(bool(n.filename) for n in notices), "active_reminders": active_reminders, "recent_notices": [NoticeOut.model_validate(n) for n in sorted(notices, key=lambda n: n.created_at or datetime.min, reverse=True)[:5]], "activity": activity, "demo_mode": not bool(settings.ai_base_url and settings.ai_api_key)}


@app.get("/api/admin/stats")
def admin_stats(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    total_users = db.query(func.count(User.id)).scalar() or 0
    notices = db.query(Notice).all()
    success = sum(n.status in {"completed", "needs_review"} for n in notices)
    langs = {}
    categories = {}
    for notice in notices:
        langs[notice.target_language] = langs.get(notice.target_language, 0) + 1
        categories[notice.category] = categories.get(notice.category, 0) + 1
    users = db.query(User).order_by(User.created_at.desc()).limit(100).all()
    return {"total_users": total_users, "notices_processed": len(notices), "success_rate": round(success / len(notices) * 100) if notices else 0, "failed": sum(n.status == "failed" for n in notices), "languages": [{"name": k, "value": v} for k, v in langs.items()], "categories": [{"name": k, "value": v} for k, v in categories.items()], "recent_activity": [{"title": n.title, "status": n.status, "created_at": n.created_at} for n in sorted(notices, key=lambda n: n.created_at or datetime.min, reverse=True)[:8]], "users": [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "created_at": u.created_at} for u in users], "provider": "configured" if settings.ai_base_url and settings.ai_api_key else "demo mode"}


@app.get("/api/preferences")
def get_preferences(db: Session = Depends(get_db), user: User = Depends(current_user)):
    pref = db.query(Preference).filter_by(user_id=user.id).first()
    return pref or {"language": "English", "font_scale": 100, "high_contrast": False, "reduced_motion": False, "simple_language": False}


@app.put("/api/preferences")
def update_preferences(payload: PreferenceInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    pref = db.query(Preference).filter_by(user_id=user.id).first()
    if pref is None:
        pref = Preference(user_id=user.id)
        db.add(pref)
    for key, value in payload.model_dump().items():
        setattr(pref, key, value)
    db.commit()
    db.refresh(pref)
    return {key: getattr(pref, key) for key in payload.model_dump()}


@app.get("/")
def root():
    return {"name": "ActionLens AI", "docs": "/docs", "health": "/api/health"}
