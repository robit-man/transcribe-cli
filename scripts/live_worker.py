#!/usr/bin/env python3
"""Live audio transcription worker.

Reads configuration as a JSON line from stdin, then reads raw PCM audio
data from stdin in a streaming fashion. Buffers audio into chunks and
transcribes each chunk, emitting JSON-line results to stdout.

Protocol:
  First line (stdin): JSON config
  Remaining stdin: raw PCM audio bytes
  stdout: JSON lines with transcription results

Audio format: raw PCM, configurable sample rate/channels/width.
"""

import io
import json
import struct
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np


def send(obj: dict) -> None:
    """Write a JSON line to stdout."""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def pcm_to_float32(data: bytes, sample_width: int) -> np.ndarray:
    """Convert raw PCM bytes to float32 numpy array normalized to [-1, 1]."""
    if sample_width == 2:
        # 16-bit signed integer
        samples = np.frombuffer(data, dtype=np.int16)
        return samples.astype(np.float32) / 32768.0
    elif sample_width == 4:
        # 32-bit signed integer
        samples = np.frombuffer(data, dtype=np.int32)
        return samples.astype(np.float32) / 2147483648.0
    elif sample_width == 1:
        # 8-bit unsigned
        samples = np.frombuffer(data, dtype=np.uint8)
        return (samples.astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"Unsupported sample width: {sample_width}")


def to_mono(audio: np.ndarray, channels: int) -> np.ndarray:
    """Convert multi-channel audio to mono by averaging channels."""
    if channels == 1:
        return audio
    # Reshape to (num_samples, num_channels) and average
    audio = audio.reshape(-1, channels)
    return audio.mean(axis=1)


def main() -> None:
    """Main live transcription loop."""
    # Read config from first line
    config_line = sys.stdin.buffer.readline()
    try:
        config = json.loads(config_line.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        send({"type": "error", "message": f"Invalid config: {e}"})
        return

    model_size = config.get("model", "base")
    language = config.get("language", "auto")
    sample_rate = config.get("sample_rate", 16000)
    channels = config.get("channels", 1)
    sample_width = config.get("sample_width", 2)
    chunk_duration = config.get("chunk_duration", 5)
    diarize = config.get("diarize", False)
    word_timestamps = config.get("word_timestamps", False)
    device = config.get("device", "auto")
    compute_type = config.get("compute_type", "auto")

    # Calculate chunk size in bytes
    bytes_per_sample = sample_width * channels
    bytes_per_second = sample_rate * bytes_per_sample
    chunk_bytes = int(chunk_duration * bytes_per_second)

    # Load model
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
    except Exception as e:
        send({"type": "error", "message": f"Failed to load model: {e}"})
        return

    send({"type": "ready"})

    # Read audio data in chunks
    audio_buffer = bytearray()
    segment_id = 0
    cumulative_time = 0.0

    try:
        while True:
            data = sys.stdin.buffer.read(4096)
            if not data:
                break

            audio_buffer.extend(data)

            # Process when we have enough data for a chunk
            while len(audio_buffer) >= chunk_bytes:
                chunk_data = bytes(audio_buffer[:chunk_bytes])
                audio_buffer = audio_buffer[chunk_bytes:]

                # Convert to float32 mono
                audio_array = pcm_to_float32(chunk_data, sample_width)
                audio_array = to_mono(audio_array, channels)

                # Resample to 16kHz if needed (faster-whisper expects 16kHz)
                if sample_rate != 16000:
                    # Simple resampling by interpolation
                    duration = len(audio_array) / sample_rate
                    target_len = int(duration * 16000)
                    indices = np.linspace(0, len(audio_array) - 1, target_len)
                    audio_array = np.interp(indices, np.arange(len(audio_array)), audio_array)

                # Transcribe the chunk
                lang_arg = language if language != "auto" else None
                try:
                    segments_gen, info = model.transcribe(
                        audio_array,
                        language=lang_arg,
                        word_timestamps=word_timestamps,
                    )

                    segments = []
                    text_parts = []

                    for seg in segments_gen:
                        words = []
                        if word_timestamps and seg.words:
                            for w in seg.words:
                                words.append({
                                    "word": w.word,
                                    "start": round(cumulative_time + w.start, 3),
                                    "end": round(cumulative_time + w.end, 3),
                                })

                        seg_text = seg.text.strip()
                        if seg_text:
                            text_parts.append(seg_text)
                            seg_dict = {
                                "id": segment_id,
                                "start": round(cumulative_time + seg.start, 3),
                                "end": round(cumulative_time + seg.end, 3),
                                "text": seg_text,
                            }
                            if words:
                                seg_dict["words"] = words
                            segments.append(seg_dict)
                            segment_id += 1

                    full_text = " ".join(text_parts)

                    if full_text.strip():
                        send({
                            "type": "transcript",
                            "text": full_text,
                            "segments": segments,
                            "is_final": True,
                            "timestamp": round(cumulative_time, 3),
                        })

                except Exception as e:
                    send({"type": "error", "message": f"Transcription error: {e}"})

                cumulative_time += chunk_duration

        # Process remaining audio in buffer
        if len(audio_buffer) > bytes_per_sample:
            chunk_data = bytes(audio_buffer)
            audio_array = pcm_to_float32(chunk_data, sample_width)
            audio_array = to_mono(audio_array, channels)

            if sample_rate != 16000:
                duration = len(audio_array) / sample_rate
                target_len = int(duration * 16000)
                if target_len > 0:
                    indices = np.linspace(0, len(audio_array) - 1, target_len)
                    audio_array = np.interp(indices, np.arange(len(audio_array)), audio_array)

            try:
                lang_arg = language if language != "auto" else None
                segments_gen, info = model.transcribe(
                    audio_array,
                    language=lang_arg,
                    word_timestamps=word_timestamps,
                )

                segments = []
                text_parts = []

                for seg in segments_gen:
                    words = []
                    if word_timestamps and seg.words:
                        for w in seg.words:
                            words.append({
                                "word": w.word,
                                "start": round(cumulative_time + w.start, 3),
                                "end": round(cumulative_time + w.end, 3),
                            })

                    seg_text = seg.text.strip()
                    if seg_text:
                        text_parts.append(seg_text)
                        seg_dict = {
                            "id": segment_id,
                            "start": round(cumulative_time + seg.start, 3),
                            "end": round(cumulative_time + seg.end, 3),
                            "text": seg_text,
                        }
                        if words:
                            seg_dict["words"] = words
                        segments.append(seg_dict)
                        segment_id += 1

                full_text = " ".join(text_parts)
                if full_text.strip():
                    send({
                        "type": "transcript",
                        "text": full_text,
                        "segments": segments,
                        "is_final": True,
                        "timestamp": round(cumulative_time, 3),
                    })

            except Exception as e:
                send({"type": "error", "message": f"Final chunk error: {e}"})

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
