"""Unit tests for word-level timestamps."""

from transcribe_cli.core.transcriber import (
    TranscriptionSegment,
    WordTimestamp,
    transcribe_file,
)
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers for building mock faster-whisper output
# ---------------------------------------------------------------------------

def _make_word(word: str, start: float, end: float) -> MagicMock:
    w = MagicMock()
    w.word = word
    w.start = start
    w.end = end
    return w


def _make_segment(
    start: float,
    end: float,
    text: str,
    words: list | None = None,
) -> MagicMock:
    seg = MagicMock()
    seg.start = start
    seg.end = end
    seg.text = text
    seg.words = words or []
    return seg


def _make_info(language: str = "en", duration: float = 10.0) -> MagicMock:
    info = MagicMock()
    info.language = language
    info.duration = duration
    return info


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWordTimestampsFromModel:
    """Tests for word timestamp extraction from faster-whisper output."""

    def test_words_parsed_from_segments(self, tmp_path: Path) -> None:
        """Words attached to model segments are surfaced in the result."""
        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"fake")

        segs = [
            _make_segment(
                0.0, 5.0, " Hello world",
                words=[
                    _make_word("Hello", 0.5, 1.0),
                    _make_word("world", 1.0, 2.0),
                ],
            ),
            _make_segment(
                5.0, 10.0, " Goodbye world",
                words=[
                    _make_word("Goodbye", 5.5, 6.5),
                    _make_word("world", 6.5, 7.5),
                ],
            ),
        ]
        info = _make_info()

        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter(segs), info)

        with patch("transcribe_cli.core.transcriber._get_model", return_value=mock_model):
            result = transcribe_file(audio_file, word_timestamps=True)

        assert len(result.segments) == 2
        assert len(result.segments[0].words) == 2
        assert len(result.segments[1].words) == 2
        assert result.segments[0].words[0].word == "Hello"
        assert result.segments[1].words[0].word == "Goodbye"

    def test_word_timestamps_accuracy(self, tmp_path: Path) -> None:
        """Word timestamps preserve exact float values."""
        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"fake")

        segs = [
            _make_segment(
                0.0, 5.0, " Test",
                words=[_make_word("Test", 1.23, 1.67)],
            ),
        ]
        info = _make_info()

        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter(segs), info)

        with patch("transcribe_cli.core.transcriber._get_model", return_value=mock_model):
            result = transcribe_file(audio_file, word_timestamps=True)

        assert result.segments[0].words[0].start == 1.23
        assert result.segments[0].words[0].end == 1.67

    def test_no_words_when_disabled(self, tmp_path: Path) -> None:
        """word_timestamps=False (default) produces empty words lists."""
        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"fake")

        # Even if the model returns words, we should not parse them
        segs = [
            _make_segment(
                0.0, 5.0, " Hello",
                words=[_make_word("Hello", 0.5, 1.0)],
            ),
        ]
        info = _make_info()

        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter(segs), info)

        with patch("transcribe_cli.core.transcriber._get_model", return_value=mock_model):
            result = transcribe_file(audio_file, word_timestamps=False)

        assert len(result.segments) == 1
        assert result.segments[0].words == []

    def test_words_empty_when_segment_has_no_words(self, tmp_path: Path) -> None:
        """Segments with no words field result in empty word lists."""
        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"fake")

        segs = [_make_segment(0.0, 5.0, " Hello", words=[])]
        info = _make_info()

        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter(segs), info)

        with patch("transcribe_cli.core.transcriber._get_model", return_value=mock_model):
            result = transcribe_file(audio_file, word_timestamps=True)

        assert result.segments[0].words == []

    def test_word_timestamp_type(self, tmp_path: Path) -> None:
        """Parsed words are WordTimestamp instances."""
        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"fake")

        segs = [
            _make_segment(
                0.0, 3.0, " Hi",
                words=[_make_word("Hi", 0.1, 0.5)],
            ),
        ]
        info = _make_info()

        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter(segs), info)

        with patch("transcribe_cli.core.transcriber._get_model", return_value=mock_model):
            result = transcribe_file(audio_file, word_timestamps=True)

        assert isinstance(result.segments[0].words[0], WordTimestamp)


# ---------------------------------------------------------------------------
# Direct unit tests on TranscriptionSegment / WordTimestamp (no model needed)
# ---------------------------------------------------------------------------


class TestTranscriptionSegmentWords:
    """Direct tests for segment word assignment logic."""

    def test_segment_holds_words(self) -> None:
        """TranscriptionSegment stores a list of WordTimestamp."""
        seg = TranscriptionSegment(id=0, start=0.0, end=5.0, text="Hello world")
        seg.words.append(WordTimestamp(word="Hello", start=0.5, end=1.0))
        seg.words.append(WordTimestamp(word="world", start=1.0, end=2.0))

        assert len(seg.words) == 2
        assert seg.words[0].word == "Hello"
        assert seg.words[1].word == "world"

    def test_segment_defaults_to_empty_words(self) -> None:
        """Words list defaults to empty."""
        seg = TranscriptionSegment(id=0, start=0.0, end=5.0, text="Test")
        assert seg.words == []
