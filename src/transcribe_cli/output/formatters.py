"""Output formatters for transcription results.

Implements Sprint 4: Output Formats
- TXT plain text format
- SRT subtitle format with timestamps and speaker labels
- VTT (WebVTT) format with voice tags for speakers
- JSON format with full metadata
"""

import json
from datetime import timedelta
from pathlib import Path
from typing import Literal

import srt

from transcribe_cli.core.transcriber import TranscriptionResult, TranscriptionSegment

# Type alias for all supported output formats
OutputFormat = Literal["txt", "srt", "vtt", "json"]


def _seconds_to_timedelta(seconds: float) -> timedelta:
    """Convert seconds to timedelta for SRT timestamps.

    Args:
        seconds: Time in seconds (can include milliseconds as decimals).

    Returns:
        timedelta object for use with srt library.
    """
    return timedelta(seconds=seconds)


def _seconds_to_vtt_timestamp(seconds: float) -> str:
    """Convert seconds to WebVTT timestamp format HH:MM:SS.mmm.

    Args:
        seconds: Time in seconds.

    Returns:
        Formatted timestamp string.
    """
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _has_any_speaker(segments: list[TranscriptionSegment]) -> bool:
    """Check if any segment has a speaker_id assigned."""
    return any(s.speaker_id is not None for s in segments)


def format_as_txt(result: TranscriptionResult) -> str:
    """Format transcription result as plain text.

    Args:
        result: TranscriptionResult to format.

    Returns:
        Plain text transcript.
    """
    return result.text.strip()


def format_as_srt(result: TranscriptionResult) -> str:
    """Format transcription result as SRT subtitles.

    When speaker_id is present on segments, prefixes text with [SPEAKER_XX].

    Args:
        result: TranscriptionResult with segments.

    Returns:
        SRT formatted string with timestamps.

    Raises:
        ValueError: If no segments are available.
    """
    if not result.segments:
        # If no segments, create a single subtitle from full text
        if result.text and result.duration:
            subtitle = srt.Subtitle(
                index=1,
                start=timedelta(seconds=0),
                end=timedelta(seconds=result.duration),
                content=result.text.strip(),
            )
            return srt.compose([subtitle])
        raise ValueError(
            "Cannot create SRT: no segments available. "
            "The transcription may not have timestamp information."
        )

    has_speakers = _has_any_speaker(result.segments)

    subtitles = []
    for i, segment in enumerate(result.segments, start=1):
        text = segment.text.strip()
        if has_speakers and segment.speaker_id is not None:
            text = f"[{segment.speaker_id}] {text}"
        subtitle = srt.Subtitle(
            index=i,
            start=_seconds_to_timedelta(segment.start),
            end=_seconds_to_timedelta(segment.end),
            content=text,
        )
        subtitles.append(subtitle)

    return srt.compose(subtitles)


def format_as_vtt(result: TranscriptionResult) -> str:
    """Format transcription result as WebVTT subtitles.

    Uses <v> voice tags for speaker identification per W3C WebVTT spec.

    Args:
        result: TranscriptionResult with segments.

    Returns:
        WebVTT formatted string.

    Raises:
        ValueError: If no segments are available.
    """
    if not result.segments:
        if result.text and result.duration:
            start_ts = _seconds_to_vtt_timestamp(0)
            end_ts = _seconds_to_vtt_timestamp(result.duration)
            return f"WEBVTT\n\n{start_ts} --> {end_ts}\n{result.text.strip()}\n"
        raise ValueError(
            "Cannot create VTT: no segments available. "
            "The transcription may not have timestamp information."
        )

    has_speakers = _has_any_speaker(result.segments)

    lines = ["WEBVTT", ""]
    for segment in result.segments:
        start_ts = _seconds_to_vtt_timestamp(segment.start)
        end_ts = _seconds_to_vtt_timestamp(segment.end)
        text = segment.text.strip()
        if has_speakers and segment.speaker_id is not None:
            text = f"<v {segment.speaker_id}>{text}</v>"
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


def format_as_json(result: TranscriptionResult) -> str:
    """Format transcription result as JSON with full metadata.

    Omits null/empty optional fields for clean output.

    Args:
        result: TranscriptionResult to format.

    Returns:
        Pretty-printed JSON string.
    """
    segments_data = []
    for seg in result.segments:
        seg_dict: dict = {
            "id": seg.id,
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
        }
        if seg.speaker_id is not None:
            seg_dict["speaker"] = seg.speaker_id
        if seg.words:
            seg_dict["words"] = [
                {"word": w.word, "start": w.start, "end": w.end} for w in seg.words
            ]
        segments_data.append(seg_dict)

    output: dict = {
        "input_file": result.input_path.name,
        "language": result.language,
        "duration": result.duration,
        "word_count": result.word_count,
    }
    if result.speakers:
        output["speakers"] = result.speakers
    output["segments"] = segments_data

    return json.dumps(output, indent=2, ensure_ascii=False)


def format_transcript(
    result: TranscriptionResult,
    output_format: OutputFormat = "txt",
) -> str:
    """Format transcription result in specified format.

    Args:
        result: TranscriptionResult to format.
        output_format: Output format ("txt", "srt", "vtt", or "json").

    Returns:
        Formatted transcript string.

    Raises:
        ValueError: If format is not supported.
    """
    formatters = {
        "txt": format_as_txt,
        "srt": format_as_srt,
        "vtt": format_as_vtt,
        "json": format_as_json,
    }
    formatter = formatters.get(output_format)
    if formatter is None:
        raise ValueError(f"Unsupported output format: {output_format}")
    return formatter(result)


def save_formatted_transcript(
    result: TranscriptionResult,
    output_path: Path,
    output_format: OutputFormat = "txt",
) -> Path:
    """Format and save transcription result to file.

    Args:
        result: TranscriptionResult to save.
        output_path: Path for output file.
        output_format: Output format.

    Returns:
        Path to saved file.
    """
    content = format_transcript(result, output_format)

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path


def get_output_extension(output_format: OutputFormat) -> str:
    """Get file extension for output format.

    Args:
        output_format: Output format.

    Returns:
        File extension including dot (e.g., ".txt", ".srt").
    """
    return f".{output_format}"
