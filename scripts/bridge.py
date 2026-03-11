#!/usr/bin/env python3
"""JSON-RPC bridge for Node.js integration.

Reads JSON-line requests from stdin, processes them using the
transcribe-cli Python backend, and writes JSON-line responses to stdout.

Protocol:
  Request:  {"id": 1, "method": "transcribe", "params": {...}}\n
  Response: {"id": 1, "result": {...}}\n
  Error:    {"id": 1, "error": {"message": "..."}}\n
  Event:    {"type": "ready"}\n
"""

import json
import shutil
import sys
from pathlib import Path


def send(obj: dict) -> None:
    """Write a JSON line to stdout."""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle_transcribe(params: dict) -> dict:
    """Transcribe a single file."""
    from transcribe_cli.core.transcriber import transcribe_file
    from transcribe_cli.output.formatters import format_transcript, save_formatted_transcript

    file_path = Path(params["file"]).resolve()
    output_format = params.get("format", "json")
    output_dir = params.get("output_dir")

    # Determine output path
    output_path = None
    if output_dir:
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"{file_path.stem}.{output_format}"
    else:
        output_path = file_path.with_suffix(f".{output_format}")

    result = transcribe_file(
        input_path=file_path,
        output_path=output_path,
        language=params.get("language", "auto"),
        model_size=params.get("model", "base"),
        device=params.get("device", "auto"),
        compute_type=params.get("compute_type", "auto"),
        diarize=params.get("diarize", False),
        word_timestamps=params.get("word_timestamps", False),
    )

    # Save formatted output
    saved = save_formatted_transcript(result, output_path, output_format)

    # Build response
    segments = []
    for seg in result.segments:
        seg_dict = {
            "id": seg.id,
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
        }
        if seg.speaker_id is not None:
            seg_dict["speaker"] = seg.speaker_id
        if seg.words:
            seg_dict["words"] = [
                {"word": w.word, "start": w.start, "end": w.end}
                for w in seg.words
            ]
        segments.append(seg_dict)

    return {
        "inputFile": result.input_path.name,
        "outputFile": str(saved),
        "text": result.text,
        "language": result.language,
        "duration": result.duration,
        "wordCount": result.word_count,
        "speakers": result.speakers,
        "segments": segments,
    }


def handle_batch(params: dict) -> dict:
    """Batch transcribe a directory."""
    from transcribe_cli.core.batch import process_directory

    directory = Path(params["directory"]).resolve()
    output_dir = params.get("output_dir")
    if output_dir:
        output_dir = Path(output_dir).resolve()

    summary = process_directory(
        directory=directory,
        output_dir=output_dir,
        output_format=params.get("format", "json"),
        concurrency=params.get("concurrency", 5),
        recursive=params.get("recursive", False),
        model_size=params.get("model", "base"),
        device=params.get("device", "auto"),
        compute_type=params.get("compute_type", "auto"),
        diarize=params.get("diarize", False),
        word_timestamps=params.get("word_timestamps", False),
    )

    results = []
    for r in summary.results:
        results.append({
            "inputFile": str(r.input_path),
            "outputFile": str(r.output_path) if r.output_path else None,
            "success": r.success,
            "error": r.error,
        })

    return {
        "totalFiles": summary.total_files,
        "successful": summary.successful,
        "failed": summary.failed,
        "results": results,
    }


def handle_info(_params: dict) -> dict:
    """Get environment information."""
    import platform

    has_whisper = False
    try:
        import faster_whisper  # noqa: F401
        has_whisper = True
    except ImportError:
        pass

    has_ffmpeg = shutil.which("ffmpeg") is not None

    has_pyannote = False
    try:
        import pyannote.audio  # noqa: F401
        has_pyannote = True
    except ImportError:
        pass

    from transcribe_cli import __version__

    return {
        "version": __version__,
        "python": platform.python_version(),
        "fasterWhisper": has_whisper,
        "ffmpeg": has_ffmpeg,
        "pyannote": has_pyannote,
    }


HANDLERS = {
    "transcribe": handle_transcribe,
    "batch": handle_batch,
    "info": handle_info,
}


def main() -> None:
    """Main bridge loop."""
    # Signal ready
    send({"type": "ready"})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            send({"id": None, "error": {"message": f"Invalid JSON: {e}"}})
            continue

        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "shutdown":
            send({"id": req_id, "result": "ok"})
            break

        handler = HANDLERS.get(method)
        if handler is None:
            send({"id": req_id, "error": {"message": f"Unknown method: {method}"}})
            continue

        try:
            result = handler(params)
            send({"id": req_id, "result": result})
        except Exception as e:
            send({"id": req_id, "error": {"message": str(e)}})


if __name__ == "__main__":
    main()
