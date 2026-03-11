"""Unit tests for speaker diarization module (WO-2)."""

from pathlib import Path
from typing import runtime_checkable
from unittest.mock import MagicMock, patch

import pytest

from transcribe_cli.core.diarization import (
    DiarizationBackend,
    DiarizationError,
    DiarizationNotAvailableError,
    DiarizationSegment,
    PyAnnoteDiarizer,
    merge_diarization,
    run_diarization,
)
from transcribe_cli.core.transcriber import TranscriptionSegment


class TestDiarizationSegment:
    """Tests for DiarizationSegment dataclass."""

    def test_segment_fields(self) -> None:
        """DiarizationSegment stores speaker, start, end."""
        seg = DiarizationSegment(speaker="SPEAKER_00", start=0.0, end=5.0)
        assert seg.speaker == "SPEAKER_00"
        assert seg.start == 0.0
        assert seg.end == 5.0


class TestMergeDiarization:
    """Tests for merge_diarization function."""

    def test_merge_single_speaker(self) -> None:
        """All segments assigned to single speaker."""
        segments = [
            TranscriptionSegment(id=0, start=0.0, end=3.0, text="Hello"),
            TranscriptionSegment(id=1, start=3.0, end=6.0, text="World"),
            TranscriptionSegment(id=2, start=6.0, end=9.0, text="Test"),
        ]
        diarization = [
            DiarizationSegment(speaker="SPEAKER_00", start=0.0, end=10.0),
        ]
        merge_diarization(segments, diarization)
        assert all(s.speaker_id == "SPEAKER_00" for s in segments)

    def test_merge_two_speakers_alternating(self) -> None:
        """Two speakers, each covering half the timeline."""
        segments = [
            TranscriptionSegment(id=0, start=0.0, end=3.0, text="A1"),
            TranscriptionSegment(id=1, start=3.0, end=6.0, text="A2"),
            TranscriptionSegment(id=2, start=6.0, end=9.0, text="B1"),
            TranscriptionSegment(id=3, start=9.0, end=12.0, text="B2"),
        ]
        diarization = [
            DiarizationSegment(speaker="SPEAKER_00", start=0.0, end=6.0),
            DiarizationSegment(speaker="SPEAKER_01", start=6.0, end=12.0),
        ]
        merge_diarization(segments, diarization)
        assert segments[0].speaker_id == "SPEAKER_00"
        assert segments[1].speaker_id == "SPEAKER_00"
        assert segments[2].speaker_id == "SPEAKER_01"
        assert segments[3].speaker_id == "SPEAKER_01"

    def test_merge_overlap_uses_majority(self) -> None:
        """Speaker with majority overlap wins."""
        segments = [
            TranscriptionSegment(id=0, start=4.0, end=8.0, text="Overlap"),
        ]
        diarization = [
            DiarizationSegment(speaker="SPEAKER_00", start=0.0, end=5.0),  # 1s overlap
            DiarizationSegment(speaker="SPEAKER_01", start=5.0, end=10.0),  # 3s overlap
        ]
        merge_diarization(segments, diarization)
        assert segments[0].speaker_id == "SPEAKER_01"

    def test_merge_no_diarization_leaves_none(self) -> None:
        """Segments with no overlapping diarization keep speaker_id=None."""
        segments = [
            TranscriptionSegment(id=0, start=20.0, end=25.0, text="Late"),
        ]
        diarization = [
            DiarizationSegment(speaker="SPEAKER_00", start=0.0, end=10.0),
        ]
        merge_diarization(segments, diarization)
        assert segments[0].speaker_id is None

    def test_merge_preserves_existing_fields(self) -> None:
        """text, start, end, id unchanged after merge."""
        segments = [
            TranscriptionSegment(id=42, start=1.5, end=3.5, text="Keep me"),
        ]
        diarization = [
            DiarizationSegment(speaker="SPEAKER_00", start=0.0, end=5.0),
        ]
        merge_diarization(segments, diarization)
        assert segments[0].id == 42
        assert segments[0].start == 1.5
        assert segments[0].end == 3.5
        assert segments[0].text == "Keep me"
        assert segments[0].speaker_id == "SPEAKER_00"

    def test_diarize_returns_sorted_segments(self) -> None:
        """Merge handles unsorted diarization input correctly."""
        segments = [
            TranscriptionSegment(id=0, start=0.0, end=5.0, text="A"),
            TranscriptionSegment(id=1, start=5.0, end=10.0, text="B"),
        ]
        # Deliberately unsorted diarization
        diarization = [
            DiarizationSegment(speaker="SPEAKER_01", start=5.0, end=10.0),
            DiarizationSegment(speaker="SPEAKER_00", start=0.0, end=5.0),
        ]
        merge_diarization(segments, diarization)
        assert segments[0].speaker_id == "SPEAKER_00"
        assert segments[1].speaker_id == "SPEAKER_01"

    def test_speakers_list_populated(self) -> None:
        """Unique speakers can be collected from merged segments."""
        segments = [
            TranscriptionSegment(id=0, start=0.0, end=3.0, text="A"),
            TranscriptionSegment(id=1, start=3.0, end=6.0, text="B"),
            TranscriptionSegment(id=2, start=6.0, end=9.0, text="C"),
        ]
        diarization = [
            DiarizationSegment(speaker="SPEAKER_00", start=0.0, end=3.0),
            DiarizationSegment(speaker="SPEAKER_01", start=3.0, end=6.0),
            DiarizationSegment(speaker="SPEAKER_00", start=6.0, end=9.0),
        ]
        merge_diarization(segments, diarization)
        speakers = sorted({s.speaker_id for s in segments if s.speaker_id is not None})
        assert speakers == ["SPEAKER_00", "SPEAKER_01"]

    def test_merge_empty_diarization(self) -> None:
        """Empty diarization list leaves all speakers as None."""
        segments = [
            TranscriptionSegment(id=0, start=0.0, end=3.0, text="Hello"),
        ]
        merge_diarization(segments, [])
        assert segments[0].speaker_id is None

    def test_merge_empty_segments(self) -> None:
        """Empty segments list doesn't crash."""
        diarization = [
            DiarizationSegment(speaker="SPEAKER_00", start=0.0, end=5.0),
        ]
        merge_diarization([], diarization)  # Should not raise

    def test_merge_multiple_diarization_same_speaker(self) -> None:
        """Multiple diarization segments from same speaker accumulate overlap."""
        segments = [
            TranscriptionSegment(id=0, start=0.0, end=10.0, text="Long segment"),
        ]
        diarization = [
            DiarizationSegment(speaker="SPEAKER_00", start=0.0, end=3.0),  # 3s
            DiarizationSegment(speaker="SPEAKER_01", start=3.0, end=5.0),  # 2s
            DiarizationSegment(speaker="SPEAKER_00", start=5.0, end=10.0),  # 5s
        ]
        merge_diarization(segments, diarization)
        # SPEAKER_00 has 8s total overlap vs SPEAKER_01's 2s
        assert segments[0].speaker_id == "SPEAKER_00"


class TestDiarizationBackendProtocol:
    """Tests for DiarizationBackend protocol."""

    def test_pyannote_diarizer_is_backend(self) -> None:
        """PyAnnoteDiarizer satisfies DiarizationBackend protocol."""
        assert isinstance(PyAnnoteDiarizer(), DiarizationBackend)

    def test_custom_backend_satisfies_protocol(self) -> None:
        """Custom class with diarize method satisfies protocol."""

        class CustomDiarizer:
            def diarize(self, audio_path: Path) -> list[DiarizationSegment]:
                return []

        assert isinstance(CustomDiarizer(), DiarizationBackend)


class TestRunDiarization:
    """Tests for run_diarization function."""

    def test_run_with_custom_backend(self) -> None:
        """Custom backend is used when provided."""

        class MockBackend:
            def diarize(self, audio_path: Path) -> list[DiarizationSegment]:
                return [DiarizationSegment(speaker="SPK_0", start=0.0, end=5.0)]

        result = run_diarization(Path("test.mp3"), backend=MockBackend())
        assert len(result) == 1
        assert result[0].speaker == "SPK_0"

    def test_run_without_pyannote_raises(self) -> None:
        """Missing pyannote.audio raises DiarizationNotAvailableError."""
        with patch.dict("sys.modules", {"pyannote": None, "pyannote.audio": None}):
            diarizer = PyAnnoteDiarizer()
            with pytest.raises(DiarizationNotAvailableError, match="pip install"):
                diarizer.diarize(Path("test.mp3"))

    def test_run_backend_error_wrapped(self) -> None:
        """Backend exceptions are wrapped in DiarizationError."""

        class FailingBackend:
            def diarize(self, audio_path: Path) -> list[DiarizationSegment]:
                raise RuntimeError("GPU out of memory")

        with pytest.raises(DiarizationError, match="GPU out of memory"):
            run_diarization(Path("test.mp3"), backend=FailingBackend())


class TestDiarizationNotAvailableError:
    """Tests for DiarizationNotAvailableError."""

    def test_error_message_includes_install_instructions(self) -> None:
        """Error message tells user how to install extras."""
        error = DiarizationNotAvailableError()
        message = str(error)
        assert "pip install transcribe-cli[diarization]" in message
        assert "pyannote" in message.lower()
