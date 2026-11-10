
"""Unit tests for voice-training scoring and consent rules. No live TTS."""

from services.voice_training.audio import score_clip
from services.voice_training.jobs import TrainingJobError, create_job


def test_score_prefers_clean_mid_length_clip():
    good, _ = score_clip(duration_s=12.0, rms=0.1, peak=0.6, clip_fraction=0.0)
    quiet, notes = score_clip(duration_s=2.0, rms=0.002, peak=0.05, clip_fraction=0.0)
    clipped, clipped_notes = score_clip(duration_s=12.0, rms=0.3, peak=1.0, clip_fraction=0.04)
    assert good > quiet
    assert good > clipped
    assert "short" in notes
    assert "clipped" in clipped_notes


def test_create_job_requires_consent_and_name(tmp_path, monkeypatch):
    monkeypatch.setenv("VOICESTUDIO_TRAINING_DIR", str(tmp_path))
    # Re-import work root would already be bound; patch the module attribute.
    import services.voice_training.jobs as jobs
    jobs.WORK_ROOT = tmp_path
    payload = b"RIFF" + b"\x00" * 64
    try:
        create_job(name="Ada", language="en", consent=False, clips=[("a.wav", payload, "")])
        assert False, "expected consent error"
    except TrainingJobError as exc:
        assert "permission" in str(exc).lower() or "consent" in str(exc).lower()
    try:
        create_job(name="", language="en", consent=True, clips=[("a.wav", payload, "")])
        assert False, "expected name error"
    except TrainingJobError as exc:
        assert "name" in str(exc).lower()
