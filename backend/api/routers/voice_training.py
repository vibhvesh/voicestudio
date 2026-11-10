
"""Admin-only routes for building saved-voice reference profiles."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from api.dependencies import require_admin
from services.saved_voices.profiles import delete_native_profile
from services.saved_voices.storage import (
    SavedVoiceError,
    SavedVoiceNotFound,
    delete_voice,
    list_voices,
)
from services.voice_training.jobs import (
    TrainingJobError,
    create_job,
    get_job,
    start_job,
)

router = APIRouter(tags=["voice-training"])

_FRONTEND = (
    __import__("pathlib").Path(__file__).resolve().parents[2]
    / "services"
    / "voice_training"
    / "frontend"
)


def _front(name: str):
    path = _FRONTEND / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Voice Training page is missing.")
    return path


@router.get("/voice-training", include_in_schema=False)
@router.get("/voice-training/", include_in_schema=False)
def training_page():
    """Public shell only. Train/list/delete still require an admin session."""
    return HTMLResponse(_front("index.html").read_text(encoding="utf-8"))


@router.get("/voice-training/{asset}", include_in_schema=False)
def training_asset(asset: str):
    if asset not in {"training.js", "training.css", "index.html"}:
        raise HTTPException(status_code=404, detail="Not found.")
    if asset.endswith(".js"):
        media = "text/javascript"
    elif asset.endswith(".css"):
        media = "text/css"
    else:
        media = "text/html"
    return FileResponse(_front(asset), media_type=media)


@router.get("/api/voice-training/voices", dependencies=[Depends(require_admin)])
def list_trained_voices():
    return {"voices": [item.admin_dict() for item in list_voices()]}


@router.delete("/api/voice-training/voices/{slug}", dependencies=[Depends(require_admin)])
def remove_trained_voice(slug: str):
    try:
        voice = delete_voice(slug)
    except SavedVoiceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SavedVoiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        delete_native_profile(voice.profile_id, name=voice.name)
    except Exception:
        pass
    return {"ok": True, "slug": voice.slug}


@router.post("/api/voice-training/jobs", dependencies=[Depends(require_admin)])
async def start_training_job(
    request: Request,
    name: str = Form(...),
    language: str = Form(...),
    consent: str = Form(...),
    seed: Optional[int] = Form(42),
    clips: list[UploadFile] = File(...),
):
    form = await request.form()
    consent_value = str(consent or form.get("consent") or "").strip().lower()
    if consent_value not in {"1", "true", "on", "yes"}:
        raise HTTPException(
            status_code=400,
            detail="Consent is required: you must have this speaker's permission to clone their voice.",
        )
    payloads: list[tuple[str, bytes, str]] = []
    for index, upload in enumerate(clips):
        filename = upload.filename or f"clip-{index + 1}.wav"
        payload = await upload.read()
        transcript = str(form.get(f"transcript_{index}") or form.get(f"transcripts[{index}]") or "")
        payloads.append((filename, payload, transcript))
    try:
        job = create_job(
            name=name,
            language=language,
            consent=True,
            clips=payloads,
            seed=seed or 42,
        )
    except TrainingJobError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    start_job(job.id)
    return JSONResponse(job.public_dict(), status_code=202)


@router.get("/api/voice-training/jobs/{job_id}", dependencies=[Depends(require_admin)])
def training_job_status(job_id: str):
    try:
        job = get_job(job_id)
    except TrainingJobError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return job.public_dict()
