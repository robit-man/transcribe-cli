"""Unit tests for data model extensions (WO-1)."""

from pathlib import Path

from transcribe_cli.core.transcriber import (
    TranscriptionResult,
    TranscriptionSegment,
    WordTimestamp,
)


class TestWordTimestamp:
    """Tests for WordTimestamp dataclass."""

    def test_word_timestamp_fields(self) -> None:
        """WordTimestamp stores word, start, and end correctly."""
        wt = WordTimestamp(word="hello", start=0.0, end=0.5)
        assert wt.word == "hello"
        assert wt.start == 0.0
        assert wt.end == 0.5

    def test_word_timestamp_types(self) -> None:
        """Fields have correct types."""
        wt = WordTimestamp(word="world", start=1.2, end=1.8)
        assert isinstance(wt.word, str)
        assert isinstance(wt.start, float)
        assert isinstance(wt.end, float)


class TestTranscriptionSegmentExtended:
    """Tests for speaker_id and words fields on TranscriptionSegment."""

    def test_segment_speaker_id_default_none(self) -> None:
        """speaker_id defaults to None."""
        seg = TranscriptionSegment(id=0, start=0.0, end=1.0, text="Hello")
        assert seg.speaker_id is None

    def test_segment_speaker_id_assigned(self) -> None:
        """speaker_id can be assigned."""
        seg = TranscriptionSegment(
            id=0, start=0.0, end=1.0, text="Hello", speaker_id="SPEAKER_01"
        )
        assert seg.speaker_id == "SPEAKER_01"

    def test_segment_words_default_empty(self) -> None:
        """words defaults to empty list."""
        seg = TranscriptionSegment(id=0, start=0.0, end=1.0, text="Hello")
        assert seg.words == []

    def test_segment_words_populated(self) -> None:
        """words can be populated with WordTimestamp objects."""
        words = [
            WordTimestamp(word="Hello", start=0.0, end=0.3),
            WordTimestamp(word="world", start=0.3, end=0.6),
            WordTimestamp(word="today", start=0.6, end=1.0),
        ]
        seg = TranscriptionSegment(
            id=0, start=0.0, end=1.0, text="Hello world today", words=words
        )
        assert len(seg.words) == 3
        for w in seg.words:
            assert w.start < w.end

    def test_backward_compat_no_speaker_no_words(self) -> None:
        """Creating segment with only (id, start, end, text) still works."""
        seg = TranscriptionSegment(id=5, start=10.0, end=15.0, text="Test text")
        assert seg.id == 5
        assert seg.start == 10.0
        assert seg.end == 15.0
        assert seg.text == "Test text"
        assert seg.speaker_id is None
        assert seg.words == []
        assert seg.duration == 5.0

    def test_words_list_is_independent(self) -> None:
        """Each segment gets its own words list (no shared default)."""
        seg1 = TranscriptionSegment(id=0, start=0.0, end=1.0, text="A")
        seg2 = TranscriptionSegment(id=1, start=1.0, end=2.0, text="B")
        seg1.words.append(WordTimestamp(word="A", start=0.0, end=1.0))
        assert len(seg1.words) == 1
        assert len(seg2.words) == 0


class TestTranscriptionResultExtended:
    """Tests for speakers field on TranscriptionResult."""

    def test_result_speakers_list(self) -> None:
        """speakers list is populated correctly."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.txt"),
            text="Hello",
            segments=[],
            language="en",
            duration=1.0,
            speakers=["SPEAKER_00", "SPEAKER_01"],
        )
        assert result.speakers == ["SPEAKER_00", "SPEAKER_01"]

    def test_result_speakers_default_empty(self) -> None:
        """speakers defaults to empty list."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.txt"),
            text="Hello",
            segments=[],
            language="en",
            duration=1.0,
        )
        assert result.speakers == []

    def test_result_backward_compat(self) -> None:
        """Existing code creating TranscriptionResult without speakers still works."""
        result = TranscriptionResult(
            input_path=Path("input.mp3"),
            output_path=Path("output.txt"),
            text="Hello world",
            segments=[],
            language="en",
            duration=5.5,
        )
        assert result.word_count == 2
        assert result.speakers == []
