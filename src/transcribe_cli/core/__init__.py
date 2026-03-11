"""Core processing modules for transcribe-cli."""

from .batch import (
    BatchResult,
    BatchSummary,
    process_batch,
    process_directory,
    scan_directory,
)
from .diarization import (
    DiarizationBackend,
    DiarizationError,
    DiarizationNotAvailableError,
    DiarizationSegment,
    PyAnnoteDiarizer,
    merge_diarization,
    run_diarization,
)
from .extractor import (
    AUDIO_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    VIDEO_EXTENSIONS,
    ExtractionError,
    ExtractionResult,
    MediaInfo,
    NoAudioStreamError,
    UnsupportedFormatError,
    extract_audio,
    get_media_info,
    is_audio_file,
    is_supported_file,
    is_video_file,
)
from .ffmpeg import (
    FFmpegInfo,
    FFmpegNotFoundError,
    FFmpegVersionError,
    check_ffmpeg_available,
    validate_ffmpeg,
)
from .transcriber import (
    TranscriptionError,
    TranscriptionResult,
    TranscriptionSegment,
    WordTimestamp,
    save_transcript,
    transcribe_file,
)

__all__ = [
    # FFmpeg
    "FFmpegInfo",
    "FFmpegNotFoundError",
    "FFmpegVersionError",
    "validate_ffmpeg",
    "check_ffmpeg_available",
    # Extractor
    "ExtractionError",
    "ExtractionResult",
    "MediaInfo",
    "NoAudioStreamError",
    "UnsupportedFormatError",
    "extract_audio",
    "get_media_info",
    "is_audio_file",
    "is_video_file",
    "is_supported_file",
    # Transcriber
    "TranscriptionError",
    "TranscriptionResult",
    "TranscriptionSegment",
    "WordTimestamp",
    "transcribe_file",
    "save_transcript",
    # Diarization
    "DiarizationBackend",
    "DiarizationError",
    "DiarizationNotAvailableError",
    "DiarizationSegment",
    "PyAnnoteDiarizer",
    "merge_diarization",
    "run_diarization",
    # Batch
    "BatchResult",
    "BatchSummary",
    "process_batch",
    "process_directory",
    "scan_directory",
    # Constants
    "VIDEO_EXTENSIONS",
    "AUDIO_EXTENSIONS",
    "SUPPORTED_EXTENSIONS",
]
