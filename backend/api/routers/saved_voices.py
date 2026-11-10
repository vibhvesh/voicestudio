"""HTTP routes for saved clone voices: GET/POST /voices, DELETE /voices/{slug}."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.dependencies import require_admin
from services.saved_voices.processing import ProcessingError, process_reference
from services.saved_voices.profiles import delete_native_profile, sync_native_profile
from services.saved_voices.storage import (
    SavedVoiceError,
    SavedVoiceExists,
    SavedVoiceNotFound,
    delete_voice,
    get_voice,
    list_voices,
    slugify,
    upsert_voice,
    validate_slug,
)

router = APIRouter(tags=["saved-voices"])


@router.get("/voices", dependencies=[Depends(require_admin)])
def list_saved_voices():
    """List saved voices. Response never includes filesystem paths or secrets."""
    return {"voices": [item.admin_dict() for item in list_voices()]}


@router.get("/voices/{slug}", dependencies=[Depends(require_admin)])
def get_saved_voice(slug: str):
    try:
        return get_voice(slug).admin_dict()
    except SavedVoiceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/voices", dependencies=[Depends(require_admin)])
async def create_saved_voice(
    name: str = Form(...),
    ref_audio: UploadFile = File(...),
    ref_text: str = Form(...),
    language: str = Form("hi"),
    seed: Optional[int] = Form(42),
    slug: Optional[str] = Form(None),
    engine: str = Form("omnivoice"),
    num_step: int = Form(16),
    speed: float = Form(1.0),
    replace: bool = Form(True),
):
    """Create or replace a saved voice. Admin only.

    The uploaded clip is trimmed, capped at 20 s, denoised, and stored under
    ``/var/lib/voicestudio/voices/<slug>/``. A native ``kind=clone`` profile is
    created or updated so the official VoiceStudio UI can use the same voice.
    """
    name = (name or "").strip()
    transcript = (ref_text or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="A voice needs a name.")
    if not transcript:
        raise HTTPException(
            status_code=400,
            detail="Please paste a transcript of the reference clip.",
        )
    try:
        slug_value = validate_slug(slug) if slug else slugify(name)
    except SavedVoiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    suffix = Path(ref_audio.filename or "reference.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(await ref_audio.read())
        raw_path = Path(handle.name)
    processed_path = Path(str(raw_path) + ".clean.wav")
    try:
        processed, duration = process_reference(raw_path, processed_path)
        try:
            existing = get_voice(slug_value)
            if not replace:
                raise SavedVoiceExists(f"A voice named {slug_value!r} already exists.")
            profile_id = existing.profile_id
        except SavedVoiceNotFound:
            profile_id = None
        voice = upsert_voice(
            name=name,
            slug=slug_value,
            language=(language or "hi").strip() or "hi",
            seed=seed,
            ref_wav=processed,
            ref_text=transcript,
            duration_s=duration,
            engine=engine or "omnivoice",
            num_step=int(num_step or 16),
            speed=float(speed or 1.0),
            instruct=None,
            profile_id=profile_id,
            source="admin",
            replace=replace,
        )
        profile_id = sync_native_profile(voice)
        if profile_id != voice.profile_id:
            voice = upsert_voice(
                name=voice.name,
                slug=voice.slug,
                language=voice.language,
                seed=voice.seed,
                ref_wav=voice.ref_wav,
                ref_text=voice.ref_text,
                duration_s=voice.duration_s,
                engine=voice.engine,
                num_step=voice.num_step,
                speed=voice.speed,
                instruct=None,
                profile_id=profile_id,
                source=voice.source,
                created_at=voice.created_at,
                replace=True,
            )
        return voice.admin_dict()
    except SavedVoiceExists as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (SavedVoiceError, ProcessingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        for path in (raw_path, processed_path):
            try:
                Path(path).unlink()
            except OSError:
                pass


@router.delete("/voices/{slug}", dependencies=[Depends(require_admin)])
def remove_saved_voice(slug: str):
    """Delete a saved voice and its synced native profile. Admin only."""
    try:
        item = delete_voice(slug)
    except SavedVoiceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    delete_native_profile(item.profile_id, name=item.name)
    return {"ok": True, "slug": item.slug}
