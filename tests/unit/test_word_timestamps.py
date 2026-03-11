"""Unit tests for word-level timestamps (WO-6)."""

from transcribe_cli.core.transcriber import (
    TranscriptionSegment,
    WordTimestamp,
    _assign_words_to_segments,
    _parse_segments,
)


class TestParseWordsFromResponse:
    """Tests for word timestamp parsing from API response."""

    def test_parse_words_from_response(self) -> None:
        """Words are parsed and assigned to segments."""
        response = {
            "segments": [
                {"id": 0, "start": 0.0, "end": 5.0, "text": " Hello world"},
                {"id": 1, "start": 5.0, "end": 10.0, "text": " Goodbye world"},
            ],
            "words": [
                {"word": "Hello", "start": 0.5, "end": 1.0},
                {"word": "world", "start": 1.0, "end": 2.0},
                {"word": "Goodbye", "start": 5.5, "end": 6.5},
                {"word": "world", "start": 6.5, "end": 7.5},
            ],
        }
        segments = _parse_segments(response, word_timestamps=True)
        assert len(segments) == 2
        assert len(segments[0].words) == 2
        assert len(segments[1].words) == 2
        assert segments[0].words[0].word == "Hello"
        assert segments[1].words[0].word == "Goodbye"

    def test_words_assigned_to_correct_segments(self) -> None:
        """Words at specific times end up in correct segments."""
        segments = [
            TranscriptionSegment(id=0, start=0.0, end=5.0, text="Seg 1"),
            TranscriptionSegment(id=1, start=5.0, end=10.0, text="Seg 2"),
        ]
        raw_words = [
            {"word": "w1", "start": 1.0, "end": 1.5},
            {"word": "w2", "start": 3.0, "end": 3.5},
            {"word": "w3", "start": 6.0, "end": 6.5},
            {"word": "w4", "start": 8.0, "end": 8.5},
        ]
        _assign_words_to_segments(segments, raw_words)
        assert len(segments[0].words) == 2
        assert len(segments[1].words) == 2
        assert segments[0].words[0].word == "w1"
        assert segments[0].words[1].word == "w2"
        assert segments[1].words[0].word == "w3"
        assert segments[1].words[1].word == "w4"

    def test_word_timestamps_accuracy(self) -> None:
        """Word timestamps preserve exact values."""
        segments = [
            TranscriptionSegment(id=0, start=0.0, end=5.0, text="Test"),
        ]
        raw_words = [{"word": "Test", "start": 1.23, "end": 1.67}]
        _assign_words_to_segments(segments, raw_words)
        assert segments[0].words[0].start == 1.23
        assert segments[0].words[0].end == 1.67

    def test_no_words_when_disabled(self) -> None:
        """word_timestamps=False (default) produces empty words."""
        response = {
            "segments": [
                {"id": 0, "start": 0.0, "end": 5.0, "text": " Hello"},
            ],
            "words": [
                {"word": "Hello", "start": 0.5, "end": 1.0},
            ],
        }
        segments = _parse_segments(response, word_timestamps=False)
        assert len(segments) == 1
        assert segments[0].words == []

    def test_words_empty_when_api_omits(self) -> None:
        """No 'words' key in API response doesn't crash."""
        response = {
            "segments": [
                {"id": 0, "start": 0.0, "end": 5.0, "text": " Hello"},
            ],
        }
        segments = _parse_segments(response, word_timestamps=True)
        assert len(segments) == 1
        assert segments[0].words == []

    def test_word_at_segment_boundary_goes_to_earlier(self) -> None:
        """Word starting exactly at segment start goes to that segment."""
        segments = [
            TranscriptionSegment(id=0, start=0.0, end=5.0, text="A"),
            TranscriptionSegment(id=1, start=5.0, end=10.0, text="B"),
        ]
        raw_words = [
            {"word": "boundary", "start": 5.0, "end": 5.5},
        ]
        _assign_words_to_segments(segments, raw_words)
        # start=5.0 falls in segment 1 (5.0 <= 5.0 < 10.0)
        assert len(segments[0].words) == 0
        assert len(segments[1].words) == 1

    def test_word_after_all_segments_goes_to_last(self) -> None:
        """Word outside all segment ranges goes to last segment."""
        segments = [
            TranscriptionSegment(id=0, start=0.0, end=5.0, text="Only"),
        ]
        raw_words = [
            {"word": "orphan", "start": 10.0, "end": 10.5},
        ]
        _assign_words_to_segments(segments, raw_words)
        assert len(segments[0].words) == 1
        assert segments[0].words[0].word == "orphan"
