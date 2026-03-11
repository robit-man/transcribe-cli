"""Transcription client for OpenAI Whisper API.

Implements Sprint 3: Transcription Client
- OpenAI Whisper API integration
- Retry logic with exponential backoff
- Response parsing with timestamps
"""

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .extractor import extract_audio, is_video_file
from .ffmpeg import FFmpegNotFoundError


class TranscriptionError(Exception):
    """Raised when transcription fails."""

    pass


class APIKeyMissingError(Exception):
    """Raised when OpenAI API key is not configured."""

    def __init__(self) -> None:
        message = (
            "OpenAI API key is not configured.\n\n"
            "Set the OPENAI_API_KEY environment variable:\n"
            "  export OPENAI_API_KEY=sk-your-api-key-here\n\n"
            "Or create a .env file with:\n"
            "  OPENAI_API_KEY=sk-your-api-key-here\n\n"
            "Get your API key at: https://platform.openai.com/api-keys"
        )
        super().__init__(message)


class FileTooLargeError(Exception):
    """Raised when file exceeds Whisper API size limit."""

    def __init__(self, path: Path, size_mb: float, max_mb: float = 25.0) -> None:
        message = (
            f"File is too large for Whisper API: {size_mb:.1f}MB\n"
            f"Maximum allowed size: {max_mb}MB\n"
            f"File: {path}\n\n"
            "For large files, use chunking (available in future release)."
        )
        super().__init__(message)
        self.path = path
        self.size_mb = size_mb
        self.max_mb = max_mb


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


# Maximum file size for Whisper API (25MB)
MAX_FILE_SIZE_MB = 25.0
MAX_FILE_SIZE_BYTES = int(MAX_FILE_SIZE_MB * 1024 * 1024)


def _check_file_size(path: Path) -> None:
    """Check if file is within Whisper API limits.

    Args:
        path: Path to audio file.

    Raises:
        FileTooLargeError: If file exceeds 25MB limit.
    """
    size = path.stat().st_size
    size_mb = size / (1024 * 1024)
    if size > MAX_FILE_SIZE_BYTES:
        raise FileTooLargeError(path, size_mb, MAX_FILE_SIZE_MB)


def _create_client(api_key: Optional[str] = None) -> OpenAI:
    """Create OpenAI client.

    Args:
        api_key: Optional API key. If not provided, uses OPENAI_API_KEY env var.

    Returns:
        Configured OpenAI client.

    Raises:
        APIKeyMissingError: If no API key is available.
    """
    try:
        client = OpenAI(api_key=api_key)
        # Validate key is present (OpenAI client doesn't validate until first call)
        if not client.api_key:
            raise APIKeyMissingError()
        return client
    except Exception as e:
        if "api_key" in str(e).lower():
            raise APIKeyMissingError() from e
        raise


@retry(
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def _transcribe_audio_file(
    client: OpenAI,
    audio_path: Path,
    language: Optional[str] = None,
    response_format: Literal["json", "text", "verbose_json"] = "verbose_json",
    word_timestamps: bool = False,
) -> dict:
    """Call Whisper API to transcribe audio file.

    Args:
        client: OpenAI client.
        audio_path: Path to audio file.
        language: Optional language code (e.g., "en", "es").
        response_format: API response format.
        word_timestamps: Whether to request word-level timestamps.

    Returns:
        API response as dictionary.

    Raises:
        RateLimitError: On rate limit (will be retried).
        APIConnectionError: On connection issues (will be retried).
        APIStatusError: On other API errors.
    """
    with open(audio_path, "rb") as audio_file:
        kwargs: dict = {
            "model": "whisper-1",
            "file": audio_file,
            "response_format": response_format,
        }
        if language and language != "auto":
            kwargs["language"] = language
        if word_timestamps and response_format == "verbose_json":
            kwargs["timestamp_granularities"] = ["segment", "word"]

        response = client.audio.transcriptions.create(**kwargs)

    # Handle different response formats
    if response_format == "text":
        return {"text": response}
    elif hasattr(response, "model_dump"):
        return response.model_dump()
    else:
        return dict(response)


def _parse_segments(
    response: dict, word_timestamps: bool = False
) -> list[TranscriptionSegment]:
    """Parse segments from Whisper API response.

    Args:
        response: API response dictionary.
        word_timestamps: Whether to parse word-level timestamps.

    Returns:
        List of TranscriptionSegment objects.
    """
    segments = []
    raw_segments = response.get("segments", [])

    for i, seg in enumerate(raw_segments):
        segments.append(
            TranscriptionSegment(
                id=seg.get("id", i),
                start=seg.get("start", 0.0),
                end=seg.get("end", 0.0),
                text=seg.get("text", "").strip(),
            )
        )

    # Assign word-level timestamps to segments if available
    if word_timestamps:
        raw_words = response.get("words", [])
        _assign_words_to_segments(segments, raw_words)

    return segments


def _assign_words_to_segments(
    segments: list[TranscriptionSegment], raw_words: list[dict]
) -> None:
    """Assign word timestamps to their parent segments by time overlap.

    Args:
        segments: List of transcription segments.
        raw_words: List of raw word dicts from API with word, start, end.
    """
    for raw_word in raw_words:
        word = WordTimestamp(
            word=raw_word.get("word", ""),
            start=raw_word.get("start", 0.0),
            end=raw_word.get("end", 0.0),
        )
        # Find the segment this word belongs to (word start falls within segment)
        for seg in segments:
            if seg.start <= word.start < seg.end:
                seg.words.append(word)
                break
        else:
            # If no segment matched, assign to last segment if any
            if segments:
                segments[-1].words.append(word)


def transcribe_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    language: str = "auto",
    api_key: Optional[str] = None,
    diarize: bool = False,
    word_timestamps: bool = False,
) -> TranscriptionResult:
    """Transcribe an audio or video file.

    For video files, audio is automatically extracted first.

    Args:
        input_path: Path to audio or video file.
        output_path: Optional path for output text file.
        language: Language code or "auto" for detection.
        api_key: Optional OpenAI API key.
        diarize: Whether to run speaker diarization.
        word_timestamps: Whether to extract word-level timestamps.

    Returns:
        TranscriptionResult with transcribed text and metadata.

    Raises:
        APIKeyMissingError: If API key not configured.
        FileTooLargeError: If file exceeds 25MB.
        FFmpegNotFoundError: If FFmpeg needed but not installed.
        TranscriptionError: If transcription fails.
    """
    input_path = Path(input_path).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")

    # Create client (validates API key)
    client = _create_client(api_key)

    # Handle video files - extract audio first
    audio_path = input_path
    temp_audio = None

    try:
        if is_video_file(input_path):
            # Extract audio to temporary file
            temp_dir = tempfile.mkdtemp(prefix="transcribe_")
            temp_audio = Path(temp_dir) / f"{input_path.stem}.mp3"
            extraction_result = extract_audio(
                input_path=input_path,
                output_path=temp_audio,
                output_format="mp3",
            )
            audio_path = extraction_result.output_path

        # Check file size
        _check_file_size(audio_path)

        # Call Whisper API
        try:
            response = _transcribe_audio_file(
                client=client,
                audio_path=audio_path,
                language=language if language != "auto" else None,
                word_timestamps=word_timestamps,
            )
        except RateLimitError as e:
            raise TranscriptionError(
                f"Rate limit exceeded after retries. Please wait and try again.\n{e}"
            ) from e
        except APIStatusError as e:
            raise TranscriptionError(f"API error: {e.message}") from e
        except APIConnectionError as e:
            raise TranscriptionError(
                f"Connection error after retries. Check your internet connection.\n{e}"
            ) from e

        # Parse response
        text = response.get("text", "")
        segments = _parse_segments(response, word_timestamps=word_timestamps)
        detected_language = response.get("language", "unknown")
        duration = response.get("duration")

        # Run speaker diarization if requested
        speakers: list[str] = []
        if diarize:
            from .diarization import DiarizationError, merge_diarization, run_diarization

            try:
                diarization_segments = run_diarization(audio_path)
                merge_diarization(segments, diarization_segments)
                speakers = sorted(
                    {s.speaker_id for s in segments if s.speaker_id is not None}
                )
            except DiarizationError as e:
                raise TranscriptionError(f"Diarization failed: {e}") from e

        # Determine output path
        if output_path is None:
            output_path = input_path.with_suffix(".txt")

        return TranscriptionResult(
            input_path=input_path,
            output_path=output_path,
            text=text,
            segments=segments,
            language=detected_language,
            duration=duration,
            speakers=speakers,
        )

    finally:
        # Clean up temporary audio file
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
