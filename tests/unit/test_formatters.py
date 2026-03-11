"""Unit tests for output formatters."""

import json
from datetime import timedelta
from pathlib import Path

import pytest
import srt

from transcribe_cli.core.transcriber import (
    TranscriptionResult,
    TranscriptionSegment,
    WordTimestamp,
)
from transcribe_cli.output.formatters import (
    _seconds_to_timedelta,
    _seconds_to_vtt_timestamp,
    format_as_json,
    format_as_srt,
    format_as_txt,
    format_as_vtt,
    format_transcript,
    get_output_extension,
    save_formatted_transcript,
)


class TestSecondsToTimedelta:
    """Tests for timestamp conversion."""

    def test_zero_seconds(self) -> None:
        """Zero seconds converts correctly."""
        result = _seconds_to_timedelta(0.0)
        assert result == timedelta(seconds=0)

    def test_whole_seconds(self) -> None:
        """Whole seconds convert correctly."""
        result = _seconds_to_timedelta(5.0)
        assert result == timedelta(seconds=5)

    def test_milliseconds(self) -> None:
        """Milliseconds are preserved."""
        result = _seconds_to_timedelta(1.5)
        assert result == timedelta(seconds=1.5)

    def test_minutes(self) -> None:
        """Minutes convert correctly."""
        result = _seconds_to_timedelta(125.0)
        assert result == timedelta(minutes=2, seconds=5)

    def test_hours(self) -> None:
        """Hours convert correctly."""
        result = _seconds_to_timedelta(3665.5)
        assert result == timedelta(hours=1, minutes=1, seconds=5, milliseconds=500)


class TestFormatAsTxt:
    """Tests for TXT formatter."""

    def test_simple_text(self) -> None:
        """Simple text is returned unchanged."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.txt"),
            text="Hello world.",
            segments=[],
            language="en",
            duration=5.0,
        )
        assert format_as_txt(result) == "Hello world."

    def test_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace is stripped."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.txt"),
            text="  Hello world.  \n",
            segments=[],
            language="en",
            duration=5.0,
        )
        assert format_as_txt(result) == "Hello world."

    def test_unicode_preserved(self) -> None:
        """Unicode characters are preserved."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.txt"),
            text="Héllo wörld! 日本語",
            segments=[],
            language="en",
            duration=5.0,
        )
        assert "Héllo" in format_as_txt(result)
        assert "日本語" in format_as_txt(result)


class TestFormatAsSrt:
    """Tests for SRT formatter."""

    def test_single_segment(self) -> None:
        """Single segment formats correctly."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.srt"),
            text="Hello world.",
            segments=[
                TranscriptionSegment(id=0, start=0.0, end=2.5, text="Hello world."),
            ],
            language="en",
            duration=2.5,
        )
        srt_output = format_as_srt(result)

        # Parse and validate
        subtitles = list(srt.parse(srt_output))
        assert len(subtitles) == 1
        assert subtitles[0].index == 1
        assert subtitles[0].content == "Hello world."

    def test_multiple_segments(self) -> None:
        """Multiple segments format correctly."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.srt"),
            text="Hello world. How are you?",
            segments=[
                TranscriptionSegment(id=0, start=0.0, end=2.0, text="Hello world."),
                TranscriptionSegment(id=1, start=2.0, end=4.0, text="How are you?"),
            ],
            language="en",
            duration=4.0,
        )
        srt_output = format_as_srt(result)

        subtitles = list(srt.parse(srt_output))
        assert len(subtitles) == 2
        assert subtitles[0].index == 1
        assert subtitles[1].index == 2
        assert subtitles[0].content == "Hello world."
        assert subtitles[1].content == "How are you?"

    def test_timestamps_format(self) -> None:
        """Timestamps are in correct SRT format."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.srt"),
            text="Test",
            segments=[
                TranscriptionSegment(id=0, start=65.5, end=68.123, text="Test"),
            ],
            language="en",
            duration=70.0,
        )
        srt_output = format_as_srt(result)

        subtitles = list(srt.parse(srt_output))
        # Check timestamps
        assert subtitles[0].start == timedelta(seconds=65.5)
        assert subtitles[0].end.total_seconds() == pytest.approx(68.123, rel=0.001)

    def test_no_segments_with_duration(self) -> None:
        """No segments but has duration creates single subtitle."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.srt"),
            text="Full transcript text.",
            segments=[],
            language="en",
            duration=10.0,
        )
        srt_output = format_as_srt(result)

        subtitles = list(srt.parse(srt_output))
        assert len(subtitles) == 1
        assert subtitles[0].content == "Full transcript text."

    def test_no_segments_no_duration_raises(self) -> None:
        """No segments and no duration raises ValueError."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.srt"),
            text="",
            segments=[],
            language="en",
            duration=None,
        )
        with pytest.raises(ValueError, match="no segments"):
            format_as_srt(result)

    def test_whitespace_stripped_from_segments(self) -> None:
        """Segment text whitespace is stripped."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.srt"),
            text="Test",
            segments=[
                TranscriptionSegment(id=0, start=0.0, end=2.0, text="  Test  "),
            ],
            language="en",
            duration=2.0,
        )
        srt_output = format_as_srt(result)
        subtitles = list(srt.parse(srt_output))
        assert subtitles[0].content == "Test"


class TestFormatTranscript:
    """Tests for format_transcript dispatcher."""

    def test_txt_format(self) -> None:
        """TXT format dispatches correctly."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.txt"),
            text="Hello",
            segments=[],
            language="en",
            duration=1.0,
        )
        output = format_transcript(result, "txt")
        assert output == "Hello"

    def test_srt_format(self) -> None:
        """SRT format dispatches correctly."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.srt"),
            text="Hello",
            segments=[
                TranscriptionSegment(id=0, start=0.0, end=1.0, text="Hello"),
            ],
            language="en",
            duration=1.0,
        )
        output = format_transcript(result, "srt")
        assert "Hello" in output
        assert "-->" in output  # SRT timestamp separator

    def test_invalid_format_raises(self) -> None:
        """Invalid format raises ValueError."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.txt"),
            text="Hello",
            segments=[],
            language="en",
            duration=1.0,
        )
        with pytest.raises(ValueError, match="Unsupported"):
            format_transcript(result, "pdf")  # type: ignore


class TestSaveFormattedTranscript:
    """Tests for saving formatted transcripts."""

    def test_save_txt(self, tmp_path: Path) -> None:
        """TXT file is saved correctly."""
        result = TranscriptionResult(
            input_path=tmp_path / "test.mp3",
            output_path=tmp_path / "test.txt",
            text="Hello world.",
            segments=[],
            language="en",
            duration=1.0,
        )
        output_path = tmp_path / "output.txt"
        saved = save_formatted_transcript(result, output_path, "txt")

        assert saved == output_path
        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == "Hello world."

    def test_save_srt(self, tmp_path: Path) -> None:
        """SRT file is saved correctly."""
        result = TranscriptionResult(
            input_path=tmp_path / "test.mp3",
            output_path=tmp_path / "test.srt",
            text="Hello",
            segments=[
                TranscriptionSegment(id=0, start=0.0, end=1.0, text="Hello"),
            ],
            language="en",
            duration=1.0,
        )
        output_path = tmp_path / "output.srt"
        saved = save_formatted_transcript(result, output_path, "srt")

        assert saved == output_path
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "Hello" in content
        assert "-->" in content

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """Parent directories are created if needed."""
        result = TranscriptionResult(
            input_path=tmp_path / "test.mp3",
            output_path=None,
            text="Test",
            segments=[],
            language="en",
            duration=1.0,
        )
        output_path = tmp_path / "nested" / "deep" / "output.txt"
        saved = save_formatted_transcript(result, output_path, "txt")

        assert saved.exists()


class TestGetOutputExtension:
    """Tests for output extension helper."""

    def test_txt_extension(self) -> None:
        """TXT returns .txt."""
        assert get_output_extension("txt") == ".txt"

    def test_srt_extension(self) -> None:
        """SRT returns .srt."""
        assert get_output_extension("srt") == ".srt"

    def test_vtt_extension(self) -> None:
        """VTT returns .vtt."""
        assert get_output_extension("vtt") == ".vtt"

    def test_json_extension(self) -> None:
        """JSON returns .json."""
        assert get_output_extension("json") == ".json"


# ──────────────────────────────────────────────────────────
# WO-3: SRT Speaker Labels
# ──────────────────────────────────────────────────────────


class TestSrtSpeakerLabels:
    """Tests for speaker labels in SRT output."""

    def test_srt_with_speaker_labels(self) -> None:
        """SRT output includes speaker labels when present."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.srt"),
            text="Hello. Goodbye.",
            segments=[
                TranscriptionSegment(
                    id=0, start=0.0, end=2.0, text="Hello.", speaker_id="SPEAKER_00"
                ),
                TranscriptionSegment(
                    id=1, start=2.0, end=4.0, text="Goodbye.", speaker_id="SPEAKER_01"
                ),
            ],
            language="en",
            duration=4.0,
        )
        srt_output = format_as_srt(result)
        assert "[SPEAKER_00]" in srt_output
        assert "[SPEAKER_01]" in srt_output
        # Still parseable
        subtitles = list(srt.parse(srt_output))
        assert len(subtitles) == 2

    def test_srt_no_speaker_labels_when_none(self) -> None:
        """SRT output has no speaker labels when speaker_id is None."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.srt"),
            text="Hello.",
            segments=[
                TranscriptionSegment(id=0, start=0.0, end=2.0, text="Hello."),
            ],
            language="en",
            duration=2.0,
        )
        srt_output = format_as_srt(result)
        assert "[SPEAKER" not in srt_output

    def test_srt_mixed_speaker_and_none(self) -> None:
        """Mixed segments: only those with speaker_id get labels."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.srt"),
            text="Hello. Goodbye.",
            segments=[
                TranscriptionSegment(
                    id=0, start=0.0, end=2.0, text="Hello.", speaker_id="SPEAKER_00"
                ),
                TranscriptionSegment(
                    id=1, start=2.0, end=4.0, text="Goodbye."
                ),
            ],
            language="en",
            duration=4.0,
        )
        srt_output = format_as_srt(result)
        subtitles = list(srt.parse(srt_output))
        assert "[SPEAKER_00]" in subtitles[0].content
        assert "[" not in subtitles[1].content

    def test_srt_speaker_labels_preserve_timestamps(self) -> None:
        """Timestamps are correct even with speaker labels."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.srt"),
            text="Hello.",
            segments=[
                TranscriptionSegment(
                    id=0, start=65.5, end=68.123, text="Hello.", speaker_id="SPEAKER_00"
                ),
            ],
            language="en",
            duration=70.0,
        )
        srt_output = format_as_srt(result)
        subtitles = list(srt.parse(srt_output))
        assert subtitles[0].start == timedelta(seconds=65.5)
        assert subtitles[0].end.total_seconds() == pytest.approx(68.123, rel=0.001)

    def test_srt_speaker_label_format(self) -> None:
        """Speaker label format is [SPEAKER_XX] prefix."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.srt"),
            text="Hi.",
            segments=[
                TranscriptionSegment(
                    id=0, start=0.0, end=1.0, text="Hi.", speaker_id="SPEAKER_02"
                ),
            ],
            language="en",
            duration=1.0,
        )
        srt_output = format_as_srt(result)
        subtitles = list(srt.parse(srt_output))
        assert subtitles[0].content == "[SPEAKER_02] Hi."


# ──────────────────────────────────────────────────────────
# WO-4: VTT Format
# ──────────────────────────────────────────────────────────


class TestVttTimestamp:
    """Tests for VTT timestamp conversion."""

    def test_zero(self) -> None:
        """Zero seconds."""
        assert _seconds_to_vtt_timestamp(0.0) == "00:00:00.000"

    def test_with_millis(self) -> None:
        """Seconds with milliseconds."""
        assert _seconds_to_vtt_timestamp(1.5) == "00:00:01.500"

    def test_minutes_and_hours(self) -> None:
        """Hours, minutes, seconds."""
        assert _seconds_to_vtt_timestamp(3665.5) == "01:01:05.500"


class TestFormatAsVtt:
    """Tests for WebVTT formatter."""

    def test_vtt_header(self) -> None:
        """Output starts with WEBVTT header."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.vtt"),
            text="Hello.",
            segments=[
                TranscriptionSegment(id=0, start=0.0, end=2.0, text="Hello."),
            ],
            language="en",
            duration=2.0,
        )
        vtt_output = format_as_vtt(result)
        assert vtt_output.startswith("WEBVTT\n\n")

    def test_vtt_single_segment(self) -> None:
        """Single segment produces valid VTT cue."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.vtt"),
            text="Hello.",
            segments=[
                TranscriptionSegment(id=0, start=0.0, end=2.5, text="Hello."),
            ],
            language="en",
            duration=2.5,
        )
        vtt_output = format_as_vtt(result)
        assert "-->" in vtt_output
        assert "Hello." in vtt_output

    def test_vtt_multiple_segments(self) -> None:
        """Multiple segments produce multiple cues."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.vtt"),
            text="A B C",
            segments=[
                TranscriptionSegment(id=0, start=0.0, end=1.0, text="A"),
                TranscriptionSegment(id=1, start=1.0, end=2.0, text="B"),
                TranscriptionSegment(id=2, start=2.0, end=3.0, text="C"),
            ],
            language="en",
            duration=3.0,
        )
        vtt_output = format_as_vtt(result)
        assert vtt_output.count("-->") == 3

    def test_vtt_timestamps_format(self) -> None:
        """VTT timestamps use correct format HH:MM:SS.mmm."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.vtt"),
            text="Test",
            segments=[
                TranscriptionSegment(id=0, start=65.5, end=68.123, text="Test"),
            ],
            language="en",
            duration=70.0,
        )
        vtt_output = format_as_vtt(result)
        assert "00:01:05.500 --> 00:01:08.123" in vtt_output

    def test_vtt_with_speaker_voice_tags(self) -> None:
        """Speaker identified with <v> voice tags."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.vtt"),
            text="Hello.",
            segments=[
                TranscriptionSegment(
                    id=0, start=0.0, end=2.0, text="Hello.", speaker_id="SPEAKER_00"
                ),
            ],
            language="en",
            duration=2.0,
        )
        vtt_output = format_as_vtt(result)
        assert "<v SPEAKER_00>" in vtt_output
        assert "</v>" in vtt_output

    def test_vtt_no_voice_tags_when_no_speakers(self) -> None:
        """No <v> tags when no speaker_id present."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.vtt"),
            text="Hello.",
            segments=[
                TranscriptionSegment(id=0, start=0.0, end=2.0, text="Hello."),
            ],
            language="en",
            duration=2.0,
        )
        vtt_output = format_as_vtt(result)
        assert "<v" not in vtt_output

    def test_vtt_format_dispatch(self) -> None:
        """format_transcript dispatches to VTT."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.vtt"),
            text="Hello.",
            segments=[
                TranscriptionSegment(id=0, start=0.0, end=2.0, text="Hello."),
            ],
            language="en",
            duration=2.0,
        )
        output = format_transcript(result, "vtt")
        assert output.startswith("WEBVTT")

    def test_vtt_no_segments_with_duration(self) -> None:
        """No segments but has duration creates single cue."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.vtt"),
            text="Full text.",
            segments=[],
            language="en",
            duration=10.0,
        )
        vtt_output = format_as_vtt(result)
        assert "WEBVTT" in vtt_output
        assert "Full text." in vtt_output

    def test_vtt_no_segments_no_duration_raises(self) -> None:
        """No segments and no duration raises ValueError."""
        result = TranscriptionResult(
            input_path=Path("test.mp3"),
            output_path=Path("test.vtt"),
            text="",
            segments=[],
            language="en",
            duration=None,
        )
        with pytest.raises(ValueError, match="no segments"):
            format_as_vtt(result)

    def test_save_vtt_file(self, tmp_path: Path) -> None:
        """VTT file is saved correctly."""
        result = TranscriptionResult(
            input_path=tmp_path / "test.mp3",
            output_path=tmp_path / "test.vtt",
            text="Hello.",
            segments=[
                TranscriptionSegment(id=0, start=0.0, end=2.0, text="Hello."),
            ],
            language="en",
            duration=2.0,
        )
        output_path = tmp_path / "output.vtt"
        saved = save_formatted_transcript(result, output_path, "vtt")
        assert saved.exists()
        content = saved.read_text(encoding="utf-8")
        assert content.startswith("WEBVTT")


# ──────────────────────────────────────────────────────────
# WO-5: JSON Format
# ──────────────────────────────────────────────────────────


class TestFormatAsJson:
    """Tests for JSON formatter."""

    def _make_result(self, **kwargs) -> TranscriptionResult:
        """Helper to create test TranscriptionResult."""
        defaults = dict(
            input_path=Path("test.mp3"),
            output_path=Path("test.json"),
            text="Hello world.",
            segments=[
                TranscriptionSegment(id=0, start=0.0, end=2.0, text="Hello world."),
            ],
            language="en",
            duration=2.0,
        )
        defaults.update(kwargs)
        return TranscriptionResult(**defaults)

    def test_json_valid_parse(self) -> None:
        """Output is valid JSON."""
        result = self._make_result()
        output = format_as_json(result)
        parsed = json.loads(output)  # Should not raise
        assert isinstance(parsed, dict)

    def test_json_top_level_fields(self) -> None:
        """Top-level keys include expected fields."""
        result = self._make_result()
        parsed = json.loads(format_as_json(result))
        assert "input_file" in parsed
        assert "language" in parsed
        assert "duration" in parsed
        assert "word_count" in parsed
        assert "segments" in parsed

    def test_json_segments_structure(self) -> None:
        """Each segment has id, start, end, text."""
        result = self._make_result()
        parsed = json.loads(format_as_json(result))
        seg = parsed["segments"][0]
        assert "id" in seg
        assert "start" in seg
        assert "end" in seg
        assert "text" in seg

    def test_json_speaker_included_when_present(self) -> None:
        """Segment with speaker_id includes 'speaker' key."""
        result = self._make_result(
            segments=[
                TranscriptionSegment(
                    id=0, start=0.0, end=2.0, text="Hello.", speaker_id="SPEAKER_00"
                ),
            ]
        )
        parsed = json.loads(format_as_json(result))
        assert parsed["segments"][0]["speaker"] == "SPEAKER_00"

    def test_json_speaker_omitted_when_none(self) -> None:
        """Segment without speaker_id omits 'speaker' key."""
        result = self._make_result()
        parsed = json.loads(format_as_json(result))
        assert "speaker" not in parsed["segments"][0]

    def test_json_words_included_when_present(self) -> None:
        """Segment with words includes 'words' array."""
        result = self._make_result(
            segments=[
                TranscriptionSegment(
                    id=0,
                    start=0.0,
                    end=2.0,
                    text="Hello world",
                    words=[
                        WordTimestamp(word="Hello", start=0.0, end=0.5),
                        WordTimestamp(word="world", start=0.5, end=1.0),
                    ],
                ),
            ]
        )
        parsed = json.loads(format_as_json(result))
        words = parsed["segments"][0]["words"]
        assert len(words) == 2
        assert words[0]["word"] == "Hello"
        assert words[0]["start"] == 0.0
        assert words[0]["end"] == 0.5

    def test_json_words_omitted_when_empty(self) -> None:
        """Segment without words omits 'words' key."""
        result = self._make_result()
        parsed = json.loads(format_as_json(result))
        assert "words" not in parsed["segments"][0]

    def test_json_speakers_list_at_top(self) -> None:
        """Top-level 'speakers' list present when speakers exist."""
        result = self._make_result(
            speakers=["SPEAKER_00", "SPEAKER_01"],
            segments=[
                TranscriptionSegment(
                    id=0, start=0.0, end=2.0, text="Hi.", speaker_id="SPEAKER_00"
                ),
                TranscriptionSegment(
                    id=1, start=2.0, end=4.0, text="Bye.", speaker_id="SPEAKER_01"
                ),
            ],
        )
        parsed = json.loads(format_as_json(result))
        assert parsed["speakers"] == ["SPEAKER_00", "SPEAKER_01"]

    def test_json_speakers_omitted_when_empty(self) -> None:
        """'speakers' key omitted when no speakers."""
        result = self._make_result()
        parsed = json.loads(format_as_json(result))
        assert "speakers" not in parsed

    def test_json_format_dispatch(self) -> None:
        """format_transcript dispatches to JSON."""
        result = self._make_result()
        output = format_transcript(result, "json")
        parsed = json.loads(output)
        assert "input_file" in parsed

    def test_save_json_file(self, tmp_path: Path) -> None:
        """JSON file is saved correctly."""
        result = self._make_result(
            input_path=tmp_path / "test.mp3",
            output_path=tmp_path / "test.json",
        )
        output_path = tmp_path / "output.json"
        saved = save_formatted_transcript(result, output_path, "json")
        assert saved.exists()
        content = json.loads(saved.read_text(encoding="utf-8"))
        assert "segments" in content

    def test_json_pretty_printed(self) -> None:
        """JSON output is indented (pretty-printed)."""
        result = self._make_result()
        output = format_as_json(result)
        assert "\n" in output
        assert "  " in output  # indent=2
