"""Speaker diarization support.

Provides speaker identification by integrating with diarization backends.
Default backend: pyannote.audio (requires optional 'diarization' extras).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from .transcriber import TranscriptionSegment


class DiarizationError(Exception):
    """Raised when diarization fails."""

    pass


class DiarizationNotAvailableError(DiarizationError):
    """Raised when diarization dependencies are not installed."""

    def __init__(self) -> None:
        message = (
            "Speaker diarization requires additional dependencies.\n\n"
            "Install with:\n"
            "  pip install transcribe-cli[diarization]\n\n"
            "This installs pyannote.audio for local speaker diarization."
        )
        super().__init__(message)


@dataclass
class DiarizationSegment:
    """A speaker-labeled time segment from diarization."""

    speaker: str
    start: float
    end: float


@runtime_checkable
class DiarizationBackend(Protocol):
    """Protocol for diarization backends."""

    def diarize(self, audio_path: Path) -> list[DiarizationSegment]:
        """Run speaker diarization on an audio file.

        Args:
            audio_path: Path to audio file.

        Returns:
            List of speaker-labeled time segments.
        """
        ...


class PyAnnoteDiarizer:
    """Speaker diarization using pyannote.audio.

    Requires pyannote.audio>=3.0 and a HuggingFace auth token
    with access to pyannote/speaker-diarization-3.1.
    """

    def __init__(self, auth_token: str | None = None) -> None:
        self._auth_token = auth_token
        self._pipeline = None

    def _load_pipeline(self) -> None:
        """Lazy-load the pyannote pipeline."""
        try:
            from pyannote.audio import Pipeline
        except ImportError:
            raise DiarizationNotAvailableError()

        self._pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=self._auth_token,
        )

    def diarize(self, audio_path: Path) -> list[DiarizationSegment]:
        """Run pyannote speaker diarization.

        Args:
            audio_path: Path to audio file.

        Returns:
            List of DiarizationSegment with speaker labels and times.
        """
        if self._pipeline is None:
            self._load_pipeline()

        diarization = self._pipeline(str(audio_path))

        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(
                DiarizationSegment(
                    speaker=speaker,
                    start=turn.start,
                    end=turn.end,
                )
            )

        # Sort by start time
        segments.sort(key=lambda s: s.start)
        return segments


def merge_diarization(
    segments: list[TranscriptionSegment],
    diarization: list[DiarizationSegment],
) -> None:
    """Assign speaker IDs to transcription segments based on time overlap.

    Uses majority overlap: each transcription segment is assigned the speaker
    who has the most overlapping time with that segment.

    Modifies segments in place.

    Args:
        segments: Transcription segments to assign speakers to.
        diarization: Diarization segments with speaker labels.
    """
    for seg in segments:
        # Calculate overlap with each speaker
        speaker_overlap: dict[str, float] = {}
        for d_seg in diarization:
            overlap_start = max(seg.start, d_seg.start)
            overlap_end = min(seg.end, d_seg.end)
            overlap = max(0.0, overlap_end - overlap_start)
            if overlap > 0:
                speaker_overlap[d_seg.speaker] = (
                    speaker_overlap.get(d_seg.speaker, 0.0) + overlap
                )

        # Assign speaker with most overlap
        if speaker_overlap:
            seg.speaker_id = max(speaker_overlap, key=speaker_overlap.get)  # type: ignore[arg-type]


def run_diarization(
    audio_path: Path,
    backend: DiarizationBackend | None = None,
    auth_token: str | None = None,
) -> list[DiarizationSegment]:
    """Run speaker diarization on an audio file.

    Args:
        audio_path: Path to audio file.
        backend: Optional custom diarization backend. Defaults to PyAnnoteDiarizer.
        auth_token: Optional HuggingFace auth token for pyannote.

    Returns:
        List of speaker-labeled time segments.

    Raises:
        DiarizationNotAvailableError: If pyannote.audio is not installed.
        DiarizationError: If diarization fails.
    """
    if backend is None:
        backend = PyAnnoteDiarizer(auth_token=auth_token)

    try:
        return backend.diarize(audio_path)
    except DiarizationNotAvailableError:
        raise
    except Exception as e:
        raise DiarizationError(f"Diarization failed: {e}") from e
