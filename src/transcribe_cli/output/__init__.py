"""Output formatting modules for transcribe-cli."""

from .formatters import (
    OutputFormat,
    format_as_json,
    format_as_srt,
    format_as_txt,
    format_as_vtt,
    format_transcript,
    get_output_extension,
    save_formatted_transcript,
)

__all__ = [
    "OutputFormat",
    "format_as_txt",
    "format_as_srt",
    "format_as_vtt",
    "format_as_json",
    "format_transcript",
    "save_formatted_transcript",
    "get_output_extension",
]
