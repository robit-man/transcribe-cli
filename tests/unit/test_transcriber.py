"""Unit tests for transcription module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcribe_cli.core.transcriber import (
    TranscriptionError,
    TranscriptionResult,
    TranscriptionSegment,
    WordTimestamp,
    save_transcript,
    transcribe_file,
)


class TestTranscriptionSegment:
    """Tests for TranscriptionSegment dataclass."""

    def test_segment_duration(self) -> None:
        """Duration is calculated correctly."""
        segment = TranscriptionSegment(id=0, start=1.5, end=4.5, text="Hello world")
        assert segment.duration == 3.0

    def test_segment_attributes(self) -> None:
        """Segment attributes are stored correctly."""
        segment = TranscriptionSegment(id=5, start=10.0, end=15.0, text="Test text")
        assert segment.id == 5
        assert segment.start == 10.0
        assert segment.end == 15.0
        assert segment.text == "Test text"


class TestTranscriptionResult:
    """Tests for TranscriptionResult dataclass."""

    def test_word_count(self) -> None:
        """Word count is calculated correctly."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.txt"),
            text="This is a test with five words.",
            segments=[],
            language="en",
            duration=10.0,
        )
        assert result.word_count == 7  # "This is a test with five words."

    def test_result_attributes(self) -> None:
        """Result attributes are stored correctly."""
        result = TranscriptionResult(
            input_path=Path("input.mp3"),
            output_path=Path("output.txt"),
            text="Hello",
            segments=[],
            language="en",
            duration=5.5,
        )
        assert result.input_path == Path("input.mp3")
        assert result.output_path == Path("output.txt")
        assert result.language == "en"
        assert result.duration == 5.5


class TestWordTimestamp:
    """Tests for WordTimestamp dataclass."""

    def test_word_timestamp_attributes(self) -> None:
        """WordTimestamp stores word and timing."""
        wt = WordTimestamp(word="hello", start=1.0, end=1.5)
        assert wt.word == "hello"
        assert wt.start == 1.0
        assert wt.end == 1.5


class TestSaveTranscript:
    """Tests for saving transcripts."""

    def test_save_creates_file(self, tmp_path: Path) -> None:
        """Transcript is saved to file."""
        result = TranscriptionResult(
            input_path=tmp_path / "input.mp3",
            output_path=tmp_path / "output.txt",
            text="Hello world.",
            segments=[],
            language="en",
            duration=5.0,
        )

        saved_path = save_transcript(result)
        assert saved_path.exists()
        assert saved_path.read_text(encoding="utf-8") == "Hello world."

    def test_save_with_custom_path(self, tmp_path: Path) -> None:
        """Transcript is saved to custom path."""
        result = TranscriptionResult(
            input_path=tmp_path / "input.mp3",
            output_path=None,
            text="Custom content.",
            segments=[],
            language="en",
            duration=5.0,
        )

        custom_path = tmp_path / "custom" / "transcript.txt"
        saved_path = save_transcript(result, custom_path)

        assert saved_path == custom_path
        assert custom_path.exists()
        assert custom_path.read_text(encoding="utf-8") == "Custom content."

    def test_save_creates_parent_directory(self, tmp_path: Path) -> None:
        """Parent directory is created if needed."""
        result = TranscriptionResult(
            input_path=tmp_path / "input.mp3",
            output_path=tmp_path / "nested" / "deep" / "output.txt",
            text="Test",
            segments=[],
            language="en",
            duration=5.0,
        )

        saved_path = save_transcript(result)
        assert saved_path.exists()

    def test_save_utf8_content(self, tmp_path: Path) -> None:
        """Non-ASCII content is saved with UTF-8 encoding."""
        result = TranscriptionResult(
            input_path=tmp_path / "input.mp3",
            output_path=tmp_path / "output.txt",
            text="Héllo wörld! 日本語",
            segments=[],
            language="en",
            duration=5.0,
        )

        saved_path = save_transcript(result)
        content = saved_path.read_text(encoding="utf-8")
        assert "Héllo" in content
        assert "日本語" in content


class TestTranscribeFileWithMocks:
    """Tests for transcribe_file with mocked faster-whisper model."""

    def _make_mock_model(self, text: str = "This is the transcribed text.", language: str = "en") -> MagicMock:
        """Build a mock WhisperModel that returns well-formed output."""
        seg1 = MagicMock()
        seg1.start = 0.0
        seg1.end = 2.0
        seg1.text = " This is"
        seg1.words = []

        seg2 = MagicMock()
        seg2.start = 2.0
        seg2.end = 4.0
        seg2.text = " the transcribed text."
        seg2.words = []

        info = MagicMock()
        info.language = language
        info.duration = 4.0

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([seg1, seg2], info)
        return mock_model

    def test_transcribe_audio_file(self, tmp_path: Path) -> None:
        """Audio file is transcribed successfully."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio content")

        mock_model = self._make_mock_model()

        with patch("transcribe_cli.core.transcriber._get_model", return_value=mock_model):
            result = transcribe_file(audio_file)

        assert "This is" in result.text
        assert "transcribed text" in result.text
        assert result.language == "en"
        assert len(result.segments) == 2

    def test_transcribe_file_not_found(self, tmp_path: Path) -> None:
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            transcribe_file(tmp_path / "nonexistent.mp3")

    def test_transcribe_model_error_raises_transcription_error(self, tmp_path: Path) -> None:
        """Model transcription failure is wrapped in TranscriptionError."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("model exploded")

        with patch("transcribe_cli.core.transcriber._get_model", return_value=mock_model):
            with pytest.raises(TranscriptionError) as exc_info:
                transcribe_file(audio_file)

        assert "Transcription failed" in str(exc_info.value)

    def test_transcribe_respects_language(self, tmp_path: Path) -> None:
        """Language parameter is forwarded to the model."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_model = self._make_mock_model()

        with patch("transcribe_cli.core.transcriber._get_model", return_value=mock_model):
            transcribe_file(audio_file, language="es")

        mock_model.transcribe.assert_called_once()
        call_kwargs = mock_model.transcribe.call_args
        assert call_kwargs.kwargs.get("language") == "es"

    def test_transcribe_auto_language_passes_none(self, tmp_path: Path) -> None:
        """language='auto' is converted to None when calling the model."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_model = self._make_mock_model()

        with patch("transcribe_cli.core.transcriber._get_model", return_value=mock_model):
            transcribe_file(audio_file, language="auto")

        call_kwargs = mock_model.transcribe.call_args
        assert call_kwargs.kwargs.get("language") is None

    def test_transcribe_with_word_timestamps(self, tmp_path: Path) -> None:
        """word_timestamps=True is forwarded to the model."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_model = self._make_mock_model()

        with patch("transcribe_cli.core.transcriber._get_model", return_value=mock_model):
            transcribe_file(audio_file, word_timestamps=True)

        call_kwargs = mock_model.transcribe.call_args
        assert call_kwargs.kwargs.get("word_timestamps") is True

    def test_transcribe_model_size_forwarded(self, tmp_path: Path) -> None:
        """model_size is forwarded to _get_model."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_model = self._make_mock_model()

        with patch("transcribe_cli.core.transcriber._get_model", return_value=mock_model) as mock_get:
            transcribe_file(audio_file, model_size="small")

        mock_get.assert_called_once_with("small", "auto", "auto")


class TestGetModel:
    """Tests for the lazy-loading model cache."""

    def test_get_model_raises_when_not_installed(self) -> None:
        """TranscriptionError is raised when faster-whisper is missing."""
        from transcribe_cli.core import transcriber

        # Clear cache to force fresh load attempt
        original_cache = transcriber._model_cache.copy()
        transcriber._model_cache.clear()

        try:
            with patch.dict("sys.modules", {"faster_whisper": None}):
                with pytest.raises(TranscriptionError, match="faster-whisper is not installed"):
                    transcriber._get_model("base", "auto", "auto")
        finally:
            transcriber._model_cache.update(original_cache)

    def test_get_model_caches_instance(self, tmp_path: Path) -> None:
        """The same model instance is returned on repeated calls."""
        from transcribe_cli.core import transcriber

        original_cache = transcriber._model_cache.copy()
        transcriber._model_cache.clear()

        mock_model = MagicMock()
        mock_whisper_module = MagicMock()
        mock_whisper_module.WhisperModel.return_value = mock_model

        try:
            with patch.dict("sys.modules", {"faster_whisper": mock_whisper_module}):
                m1 = transcriber._get_model("base", "auto", "auto")
                m2 = transcriber._get_model("base", "auto", "auto")
                assert m1 is m2
                # WhisperModel constructor called only once
                assert mock_whisper_module.WhisperModel.call_count == 1
        finally:
            transcriber._model_cache.clear()
            transcriber._model_cache.update(original_cache)
