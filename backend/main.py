"""FotoRestorer — API server for old photo restoration and colorization."""

import os
import uuid
import shutil
from pathlib import Path

from typing import List
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from storage import get_remaining, increment_usage, add_paid_photos, get_usage
from restore import restore_and_colorize, restore_from_two_photos
from payments import create_checkout_session, handle_webhook, PHOTO_PACKS

app = FastAPI(title="FotoRestorer", version="1.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure upload directories exist
UPLOAD_DIR = Path(settings.UPLOAD_DIR)
(UPLOAD_DIR / "originals").mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "results").mkdir(parents=True, exist_ok=True)


def _get_session_id(session_id: str | None) -> str:
    """Get or create a session ID for anonymous usage tracking."""
    if session_id:
        return session_id
    return str(uuid.uuid4())


# ── Status ───────────────────────────────────────────────────────────

@app.get("/api/status")
async def status(session_id: str | None = Cookie(default=None)):
    sid = _get_session_id(session_id)
    remaining = get_remaining(sid, settings.FREE_PHOTOS_LIMIT)
    usage = get_usage(sid)
    response = JSONResponse({
        "session_id": sid,
        "remaining": remaining,
        "used": usage["used"],
        "free_limit": settings.FREE_PHOTOS_LIMIT,
        "paid_photos": usage.get("paid_photos", 0),
    })
    response.set_cookie("session_id", sid, max_age=60 * 60 * 24 * 365)
    return response


# ── Upload & Restore ─────────────────────────────────────────────────

@app.post("/api/restore")
async def restore_photo(
    file: UploadFile = File(...),
    session_id: str | None = Cookie(default=None),
):
    sid = _get_session_id(session_id)
    remaining = get_remaining(sid, settings.FREE_PHOTOS_LIMIT)

    if remaining <= 0:
        raise HTTPException(
            status_code=402,
            detail="Лимит бесплатных фото исчерпан. Купите дополнительный пакет.",
        )

    # Validate file
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Файл должен быть изображением.")

    contents = await file.read()
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой. Максимум {settings.MAX_FILE_SIZE_MB} МБ.",
        )

    # Save original
    photo_id = str(uuid.uuid4())
    ext = Path(file.filename or "photo.jpg").suffix or ".jpg"
    orig_path = UPLOAD_DIR / "originals" / f"{photo_id}{ext}"
    orig_path.write_bytes(contents)

    # Process
    try:
        result_bytes = await restore_and_colorize(contents, file.filename or "photo.jpg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")

    # Save result
    result_path = UPLOAD_DIR / "results" / f"{photo_id}.jpg"
    result_path.write_bytes(result_bytes)

    # Track usage
    increment_usage(sid)

    remaining_after = get_remaining(sid, settings.FREE_PHOTOS_LIMIT)

    response = JSONResponse({
        "photo_id": photo_id,
        "download_url": f"/api/download/{photo_id}",
        "remaining": remaining_after,
    })
    response.set_cookie("session_id", sid, max_age=60 * 60 * 24 * 365)
    return response


# ── Upload 2 Photos (glare removal) ──────────────────────────────────

@app.post("/api/restore-multi")
async def restore_multi_photo(
    files: List[UploadFile] = File(...),
    session_id: str | None = Cookie(default=None),
):
    """Upload 2 photos of the same print taken at different angles.
    Merges them to remove glare, then restores and colorizes."""
    sid = _get_session_id(session_id)
    remaining = get_remaining(sid, settings.FREE_PHOTOS_LIMIT)

    if remaining <= 0:
        raise HTTPException(
            status_code=402,
            detail="Лимит бесплатных фото исчерпан. Купите дополнительный пакет.",
        )

    if len(files) != 2:
        raise HTTPException(status_code=400, detail="Нужно загрузить ровно 2 фото.")

    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    images = []
    for f in files:
        if not f.content_type or not f.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Оба файла должны быть изображениями.")
        data = await f.read()
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"Файл слишком большой. Максимум {settings.MAX_FILE_SIZE_MB} МБ.",
            )
        images.append(data)

    # Save originals
    photo_id = str(uuid.uuid4())
    for i, data in enumerate(images):
        orig_path = UPLOAD_DIR / "originals" / f"{photo_id}_angle{i+1}.jpg"
        orig_path.write_bytes(data)

    # Process: merge → preprocess → restore → colorize
    try:
        result_bytes = await restore_from_two_photos(images[0], images[1])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")

    result_path = UPLOAD_DIR / "results" / f"{photo_id}.jpg"
    result_path.write_bytes(result_bytes)

    increment_usage(sid)
    remaining_after = get_remaining(sid, settings.FREE_PHOTOS_LIMIT)

    response = JSONResponse({
        "photo_id": photo_id,
        "download_url": f"/api/download/{photo_id}",
        "remaining": remaining_after,
    })
    response.set_cookie("session_id", sid, max_age=60 * 60 * 24 * 365)
    return response


# ── Download Result ──────────────────────────────────────────────────

@app.get("/api/download/{photo_id}")
async def download_result(photo_id: str):
    result_path = UPLOAD_DIR / "results" / f"{photo_id}.jpg"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Фото не найдено.")
    return FileResponse(result_path, media_type="image/jpeg", filename=f"restored_{photo_id}.jpg")


# ── Payments ─────────────────────────────────────────────────────────

@app.get("/api/packs")
async def get_packs():
    return {"packs": PHOTO_PACKS}


@app.post("/api/checkout")
async def checkout(
    request: Request,
    session_id: str | None = Cookie(default=None),
):
    body = await request.json()
    pack_id = body.get("pack_id", "pack_10")
    sid = _get_session_id(session_id)

    base_url = str(request.base_url).rstrip("/")
    try:
        url = create_checkout_session(
            session_id=sid,
            pack_id=pack_id,
            success_url=f"{base_url}/success",
            cancel_url=f"{base_url}/",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"checkout_url": url}


@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        metadata = handle_webhook(payload, sig)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if metadata:
        sid = metadata.get("app_session_id")
        count = int(metadata.get("photo_count", "0"))
        if sid and count > 0:
            add_paid_photos(sid, count)

    return {"status": "ok"}


# ── Serve frontend in production ─────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
