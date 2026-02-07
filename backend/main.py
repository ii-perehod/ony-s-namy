"""FotoRestorer — API server for old photo restoration and colorization."""

import os
import re
import uuid
import shutil
from pathlib import Path

from typing import List
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from storage import (
    get_remaining, increment_usage, add_paid_photos, get_usage,
    set_subscription, cancel_subscription, reset_subscription_period,
)
from restore import restore_and_colorize, restore_from_two_photos
from payments import (
    create_checkout_session, create_subscription_checkout,
    handle_webhook, PHOTO_PACKS, SUBSCRIPTION_PLANS,
)

app = FastAPI(title="FotoRestorer", version="1.0.0")

UUID_RE = re.compile(r'^[a-f0-9\-]{36}$')

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
        "subscription": usage.get("subscription"),
        "sub_photo_limit": usage.get("sub_photo_limit", 0),
        "sub_used": usage.get("sub_used", 0),
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
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}") from e

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
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}") from e

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


# ── Batch Upload ─────────────────────────────────────────────────────

@app.post("/api/restore-batch")
async def restore_batch(
    files: List[UploadFile] = File(...),
    session_id: str | None = Cookie(default=None),
):
    """Upload and restore multiple photos at once. Each photo is processed
    independently through the standard pipeline."""
    sid = _get_session_id(session_id)
    remaining = get_remaining(sid, settings.FREE_PHOTOS_LIMIT)

    if remaining <= 0:
        raise HTTPException(
            status_code=402,
            detail="Лимит исчерпан. Купите пакет или оформите подписку.",
        )

    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Максимум 20 фото за раз.")

    if len(files) > remaining:
        raise HTTPException(
            status_code=402,
            detail=f"Недостаточно лимита. Осталось {remaining}, загружено {len(files)}.",
        )

    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    results = []

    for file in files:
        if not file.content_type or not file.content_type.startswith("image/"):
            results.append({"error": f"{file.filename}: не является изображением"})
            continue

        contents = await file.read()
        if len(contents) > max_bytes:
            results.append({"error": f"{file.filename}: слишком большой файл"})
            continue

        photo_id = str(uuid.uuid4())
        ext = Path(file.filename or "photo.jpg").suffix or ".jpg"
        orig_path = UPLOAD_DIR / "originals" / f"{photo_id}{ext}"
        orig_path.write_bytes(contents)

        try:
            result_bytes = await restore_and_colorize(contents, file.filename or "photo.jpg")
            result_path = UPLOAD_DIR / "results" / f"{photo_id}.jpg"
            result_path.write_bytes(result_bytes)
            increment_usage(sid)
            results.append({
                "photo_id": photo_id,
                "filename": file.filename,
                "download_url": f"/api/download/{photo_id}",
            })
        except Exception as e:
            results.append({"error": f"{file.filename}: {str(e)}"})

    remaining_after = get_remaining(sid, settings.FREE_PHOTOS_LIMIT)

    response = JSONResponse({
        "results": results,
        "remaining": remaining_after,
    })
    response.set_cookie("session_id", sid, max_age=60 * 60 * 24 * 365)
    return response


# ── Download Result ──────────────────────────────────────────────────

@app.get("/api/download/{photo_id}")
async def download_result(photo_id: str):
    if not UUID_RE.match(photo_id):
        raise HTTPException(status_code=400, detail="Неверный ID фото.")
    result_path = UPLOAD_DIR / "results" / f"{photo_id}.jpg"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Фото не найдено.")
    return FileResponse(result_path, media_type="image/jpeg", filename=f"restored_{photo_id}.jpg")


# ── Payments ─────────────────────────────────────────────────────────

@app.get("/api/packs")
async def get_packs():
    return {"packs": PHOTO_PACKS}


@app.get("/api/subscriptions")
async def get_subscriptions():
    return {"plans": SUBSCRIPTION_PLANS}


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
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"checkout_url": url}


@app.post("/api/subscribe")
async def subscribe(
    request: Request,
    session_id: str | None = Cookie(default=None),
):
    body = await request.json()
    plan_id = body.get("plan_id", "sub_30")
    sid = _get_session_id(session_id)

    base_url = str(request.base_url).rstrip("/")
    try:
        url = create_subscription_checkout(
            session_id=sid,
            plan_id=plan_id,
            success_url=f"{base_url}/success",
            cancel_url=f"{base_url}/",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    response = JSONResponse({"checkout_url": url})
    response.set_cookie("session_id", sid, max_age=60 * 60 * 24 * 365)
    return response


@app.post("/api/webhook/yookassa")
async def yookassa_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Неверный JSON") from e

    try:
        result = handle_webhook(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if result:
        event_type = result.get("event")
        sid = result.get("app_session_id")

        if event_type == "pack_purchased" and sid:
            count = int(result.get("photo_count", "0"))
            if count > 0:
                add_paid_photos(sid, count)

        elif event_type == "subscription_created" and sid:
            plan_id = result.get("plan_id", "")
            photo_limit = int(result.get("photo_limit", "0"))
            pm_id = result.get("payment_method_id", "")
            set_subscription(sid, plan_id, photo_limit, pm_id)

        elif event_type == "subscription_renewed" and sid:
            plan_id = result.get("plan_id", "")
            photo_limit = int(result.get("photo_limit", "0"))
            pm_id = result.get("payment_method_id", "")
            set_subscription(sid, plan_id, photo_limit, pm_id)

        elif event_type == "subscription_cancelled" and sid:
            cancel_subscription(sid)

    return {"status": "ok"}


# ── Serve frontend in production ─────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
