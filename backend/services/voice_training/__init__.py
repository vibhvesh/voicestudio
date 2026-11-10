"""Build an optimized clone reference from multiple clips (zero-shot, not fine-tuning)."""

from .audio import TrainingAudioError, analyze_wav, build_reference, prepare_clip, score_clip
from .jobs import TrainingJobError, create_job, get_job, list_jobs, start_job
from .transcripts import transcribe_clip

__all__ = [
    "TrainingAudioError",
    "TrainingJobError",
    "analyze_wav",
    "build_reference",
    "create_job",
    "get_job",
    "list_jobs",
    "prepare_clip",
    "score_clip",
    "start_job",
    "transcribe_clip",
]
