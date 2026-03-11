"""Transcription backend using faster-whisper local models.

Runs fully locally — no API key required.
Supports: tiny, base, small, medium, large-v3 model sizes.
"""

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .extractor import extract_audio, is_video_file
from .ffmpeg import FFmpegNotFoundError  # noqa: F401 — re-exported for callers


class TranscriptionError(Exception):
    """Raised when transcription fails."""

    pass


@dataclass
class WordTimestamp:
    """A single word with timing information."""

    word: str
    start: float
    end: float


@dataclass
class TranscriptionSegment:
    """A segment of transcribed text with timing."""

    id: int
    start: float
    end: float
    text: str
    speaker_id: Optional[str] = None
    words: list[WordTimestamp] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """Duration of segment in seconds."""
        return self.end - self.start


@dataclass
class TranscriptionResult:
    """Result of a transcription operation."""

    input_path: Path
    output_path: Optional[Path]
    text: str
    segments: list[TranscriptionSegment]
    language: str
    duration: Optional[float]
    speakers: list[str] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        """Approximate word count."""
        return len(self.text.split())


# Module-level model cache: (model_size, device, compute_type) -> WhisperModel
_model_cache: dict[tuple[str, str, str], object] = {}


def _get_model(model_size: str, device: str, compute_type: str) -> object:
    """Return a cached WhisperModel, loading it on first use.

    Args:
        model_size: Whisper model variant (e.g. "base", "large-v3").
        device: Compute device ("auto", "cpu", "cuda").
        compute_type: Precision mode ("auto", "float16", "float32", "int8").

    Returns:
        A loaded WhisperModel instance.

    Raises:
        TranscriptionError: If faster-whisper is not installed or the model
            cannot be loaded.
    """
    key = (model_size, device, compute_type)
    if key not in _model_cache:
        try:
            from faster_whisper import WhisperModel  # type: ignore[import]
        except ImportError as exc:
            raise TranscriptionError(
                "faster-whisper is not installed. "
                "Run: pip install faster-whisper"
            ) from exc

        try:
            _model_cache[key] = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
            )
        except Exception as exc:
            raise TranscriptionError(
                f"Failed to load Whisper model '{model_size}': {exc}"
            ) from exc

    return _model_cache[key]


def transcribe_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    language: str = "auto",
    model_size: str = "base",
    device: str = "auto",
    compute_type: str = "auto",
    diarize: bool = False,
    word_timestamps: bool = False,
) -> TranscriptionResult:
    """Transcribe an audio or video file using a local Whisper model.

    For video files, audio is automatically extracted first.
    No API key is required — inference runs entirely on the local machine.

    Args:
        input_path: Path to audio or video file.
        output_path: Optional path for output text file.
        language: BCP-47 language code (e.g. "en") or "auto" for detection.
        model_size: Model variant to use (tiny, base, small, medium, large-v3).
        device: Compute device — "auto", "cpu", or "cuda".
        compute_type: Precision — "auto", "float16", "float32", or "int8".
        diarize: Whether to run speaker diarization.
        word_timestamps: Whether to extract word-level timestamps.

    Returns:
        TranscriptionResult with transcribed text and metadata.

    Raises:
        FileNotFoundError: If input_path does not exist.
        FFmpegNotFoundError: If FFmpeg is needed but not installed.
        TranscriptionError: If transcription fails for any reason.
    """
    input_path = Path(input_path).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")

    model = _get_model(model_size, device, compute_type)

    audio_path = input_path
    temp_audio = None

    try:
        # Extract audio from video files
        if is_video_file(input_path):
            temp_dir = tempfile.mkdtemp(prefix="transcribe_")
            temp_audio = Path(temp_dir) / f"{input_path.stem}.mp3"
            extraction_result = extract_audio(
                input_path=input_path,
                output_path=temp_audio,
                output_format="mp3",
            )
            audio_path = extraction_result.output_path

        # Run local transcription
        lang_arg = language if language != "auto" else None
        try:
            segments_gen, info = model.transcribe(  # type: ignore[union-attr]
                str(audio_path),
                language=lang_arg,
                word_timestamps=word_timestamps,
            )
        except Exception as exc:
            raise TranscriptionError(f"Transcription failed: {exc}") from exc

        # Materialise the generator into structured segments
        segments: list[TranscriptionSegment] = []
        text_parts: list[str] = []

        for i, seg in enumerate(segments_gen):
            words: list[WordTimestamp] = []
            if word_timestamps and seg.words:
                for w in seg.words:
                    words.append(
                        WordTimestamp(
                            word=w.word,
                            start=w.start,
                            end=w.end,
                        )
                    )

            seg_text = seg.text.strip()
            text_parts.append(seg_text)

            segments.append(
                TranscriptionSegment(
                    id=i,
                    start=seg.start,
                    end=seg.end,
                    text=seg_text,
                    words=words,
                )
            )

        full_text = " ".join(text_parts)
        detected_language = info.language if info.language else "unknown"
        duration: Optional[float] = getattr(info, "duration", None)

        # Optional speaker diarization
        speakers: list[str] = []
        if diarize:
            from .diarization import DiarizationError, merge_diarization, run_diarization

            try:
                diarization_segments = run_diarization(audio_path)
                merge_diarization(segments, diarization_segments)
                speakers = sorted(
                    {s.speaker_id for s in segments if s.speaker_id is not None}
                )
            except DiarizationError as exc:
                raise TranscriptionError(f"Diarization failed: {exc}") from exc

        if output_path is None:
            output_path = input_path.with_suffix(".txt")

        return TranscriptionResult(
            input_path=input_path,
            output_path=output_path,
            text=full_text,
            segments=segments,
            language=detected_language,
            duration=duration,
            speakers=speakers,
        )

    finally:
        if temp_audio and temp_audio.exists():
            temp_audio.unlink()
            temp_audio.parent.rmdir()


def save_transcript(result: TranscriptionResult, output_path: Optional[Path] = None) -> Path:
    """Save transcription result to a text file.

    Args:
        result: TranscriptionResult to save.
        output_path: Optional output path. Uses result.output_path if not provided.

    Returns:
        Path to saved file.
    """
    path = output_path or result.output_path
    if path is None:
        path = result.input_path.with_suffix(".txt")

    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(result.text)

    return path
