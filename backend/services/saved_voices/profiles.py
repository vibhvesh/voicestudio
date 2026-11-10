"""Keep a native VoiceStudio /profiles row in sync with a saved-voice folder."""

from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

from .storage import SavedVoice


def sync_native_profile(voice: SavedVoice) -> str:
    """Create or update a kind=clone profile and return its id."""
    from core.config import VOICES_DIR
    from core.db import db_conn

    name = voice.name
    language = voice.language or "hi"
    seed = voice.seed
    ref_text = voice.ref_text or ""
    profile_id = voice.profile_id
    voices_dir = Path(VOICES_DIR)
    voices_dir.mkdir(parents=True, exist_ok=True)

    with db_conn() as conn:
        row = None
        if profile_id:
            row = conn.execute(
                "SELECT * FROM voice_profiles WHERE id=?", (profile_id,)
            ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT * FROM voice_profiles WHERE name=? AND kind='clone'",
                (name,),
            ).fetchone()
        if row is not None:
            profile_id = row["id"]
            audio_filename = row["ref_audio_path"] or f"{profile_id}.wav"
            dest = voices_dir / Path(audio_filename).name
            shutil.copyfile(voice.ref_wav, dest)
            conn.execute(
                "UPDATE voice_profiles SET ref_audio_path=?, ref_text=?, "
                "language=?, seed=?, instruct=?, kind='clone' WHERE id=?",
                (dest.name, ref_text, language, seed, "", profile_id),
            )
            return profile_id

        profile_id = str(uuid.uuid4())[:8]
        dest = voices_dir / f"{profile_id}.wav"
        shutil.copyfile(voice.ref_wav, dest)
        conn.execute(
            "INSERT INTO voice_profiles (id, name, ref_audio_path, ref_text, instruct, "
            "language, seed, personality, kind, vd_states, design_recipe, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                profile_id, name, dest.name, ref_text, "", language, seed,
                "", "clone", None, None, time.time(),
            ),
        )
    try:
        from core import event_bus
        event_bus.emit("profiles", {"action": "created", "id": profile_id})
    except Exception:
        pass
    return profile_id


def delete_native_profile(profile_id: Optional[str], *, name: Optional[str] = None) -> None:
    """Delete the synced profile row and its flat WAV, if present."""
    if not profile_id and not name:
        return
    from core.config import VOICES_DIR
    from core.db import db_conn

    with db_conn() as conn:
        row = None
        if profile_id:
            row = conn.execute(
                "SELECT * FROM voice_profiles WHERE id=?", (profile_id,)
            ).fetchone()
        if row is None and name:
            row = conn.execute(
                "SELECT * FROM voice_profiles WHERE name=? AND kind='clone'",
                (name,),
            ).fetchone()
        if row is None:
            return
        audio = row["ref_audio_path"]
        conn.execute("DELETE FROM voice_profiles WHERE id=?", (row["id"],))
    if audio:
        path = Path(VOICES_DIR) / Path(str(audio)).name
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                pass
    try:
        from core import event_bus
        event_bus.emit("profiles", {"action": "deleted", "id": row["id"]})
    except Exception:
        pass
