# V2 Work Orders: Multi-Speaker Transcription

> **Scope**: All unimplemented features for multi-speaker transcription with timestamps and speaker identity.
> **Prerequisite**: A multi-speaker test audio file (2+ distinct speakers, ~2-5 min) placed at `tests/fixtures/multi-speaker.mp3`. User to provide.

---

## Dependency Graph

```
WO-1 (Data Model)
 ├── WO-2 (Diarization Backend)
 │    ├── WO-7 (CLI/Config Flags)
 │    │    └── WO-8 (Batch Diarization)
 │    ├── WO-3 (Speaker Labels in SRT)
 │    ├── WO-4 (VTT Format + Speakers)
 │    └── WO-5 (JSON Format + Speakers)
 └── WO-6 (Word-Level Timestamps)
      ├── WO-4 (VTT Format)
      └── WO-5 (JSON Format)
```

---

## WO-1: Extend Data Model for Speaker Identity and Word Timestamps

**File**: `src/transcribe_cli/core/transcriber.py`

### Changes

1. Add `speaker_id: Optional[str] = None` field to `TranscriptionSegment` (the placeholder comment existed in architecture docs but the field was never added to code).
2. Add `WordTimestamp` dataclass with `word: str`, `start: float`, `end: float`.
3. Add `words: list[WordTimestamp] = field(default_factory=list)` to `TranscriptionSegment`.
4. Add `speakers: list[str] = field(default_factory=list)` to `TranscriptionResult` (unique speaker IDs found in result).

### Tests — `tests/unit/test_models.py` (new file)

```
test_segment_speaker_id_default_none
    Create TranscriptionSegment without speaker_id.
    Assert segment.speaker_id is None.

test_segment_speaker_id_assigned
    Create TranscriptionSegment(speaker_id="SPEAKER_01").
    Assert segment.speaker_id == "SPEAKER_01".

test_segment_words_default_empty
    Create TranscriptionSegment without words.
    Assert segment.words == [].

test_segment_words_populated
    Create segment with 3 WordTimestamp objects.
    Assert len(segment.words) == 3.
    Assert each word has start < end.

test_word_timestamp_fields
    Create WordTimestamp(word="hello", start=0.0, end=0.5).
    Assert all fields accessible and correct types.

test_result_speakers_list
    Create TranscriptionResult with speakers=["SPEAKER_01", "SPEAKER_02"].
    Assert result.speakers == ["SPEAKER_01", "SPEAKER_02"].

test_backward_compat_no_speaker_no_words
    Create TranscriptionSegment with only (id, start, end, text).
    Assert object creates successfully (no regressions to existing code).
```

### Acceptance Criteria
- All existing tests still pass (no breaking changes to TranscriptionSegment/TranscriptionResult constructors).
- New fields are optional with safe defaults.

---

## WO-2: Speaker Diarization Backend

**Files**: `src/transcribe_cli/core/diarization.py` (new), `src/transcribe_cli/core/transcriber.py` (modify)

### Design Decision: Backend Choice

The Whisper API alone does **not** provide speaker diarization. Two viable integration paths:

| Option | Pros | Cons |
|--------|------|------|
| **A) pyannote.audio** (local) | Free, no API cost, offline capable | Requires torch, large model download, GPU recommended |
| **B) External API** (Deepgram / AssemblyAI) | High accuracy, no local compute | API cost, second API key, vendor lock-in |

**Recommended**: Option A (`pyannote.audio`) with a `DiarizationBackend` protocol so Option B can be added later without changes.

### Changes

1. **New file `diarization.py`**:
   - `DiarizationBackend` Protocol with method: `diarize(audio_path: Path) -> list[DiarizationSegment]`
   - `DiarizationSegment` dataclass: `speaker: str`, `start: float`, `end: float`
   - `PyAnnoteDiarizer` class implementing the protocol (wraps `pyannote.audio` pipeline)
   - `merge_diarization(segments: list[TranscriptionSegment], diarization: list[DiarizationSegment]) -> list[TranscriptionSegment]` — assigns `speaker_id` to each transcription segment by overlapping time ranges.

2. **Modify `transcriber.py`**:
   - Add `diarize: bool = False` parameter to `transcribe_file()`.
   - When `diarize=True`, run diarization after transcription and merge results.
   - Populate `result.speakers` from unique speaker IDs.

3. **New dependency**: `pyannote.audio` added as optional dependency group `[project.optional-dependencies] diarization = ["pyannote-audio>=3.0"]`.

### Tests — `tests/unit/test_diarization.py` (new file)

```
test_merge_single_speaker
    Input: 3 transcription segments, 1 diarization segment covering all.
    Assert all segments get speaker_id == "SPEAKER_00".

test_merge_two_speakers_alternating
    Input: 4 transcription segments (0-3s, 3-6s, 6-9s, 9-12s).
    Diarization: SPEAKER_00 (0-6s), SPEAKER_01 (6-12s).
    Assert segments[0].speaker_id == "SPEAKER_00"
    Assert segments[1].speaker_id == "SPEAKER_00"
    Assert segments[2].speaker_id == "SPEAKER_01"
    Assert segments[3].speaker_id == "SPEAKER_01"

test_merge_overlap_uses_majority
    Transcription segment spans 4.0-8.0s.
    Diarization: SPEAKER_00 (0-5s), SPEAKER_01 (5-10s).
    Assert segment.speaker_id == "SPEAKER_01" (3s overlap vs 1s).

test_merge_no_diarization_leaves_none
    Input: segments with no overlapping diarization data.
    Assert segment.speaker_id is None for unmatched segments.

test_merge_preserves_existing_fields
    Assert text, start, end, id unchanged after merge.

test_diarization_backend_protocol
    Assert PyAnnoteDiarizer satisfies DiarizationBackend protocol
    (isinstance check or structural subtype check).

test_diarize_returns_sorted_segments
    Input: unsorted diarization output.
    Assert merge result has segments sorted by start time.

test_speakers_list_populated
    Run merge, collect unique speakers.
    Assert result.speakers == ["SPEAKER_00", "SPEAKER_01"] (sorted).
```

### Integration Test — `tests/integration/test_diarization_e2e.py`

```
test_diarize_multi_speaker_audio (requires fixture file + API key)
    Run transcribe_file("tests/fixtures/multi-speaker.mp3", diarize=True).
    Assert result.speakers has >= 2 entries.
    Assert every segment has a non-None speaker_id.
    Assert at least 2 different speaker_ids appear across segments.
    Print speaker timeline for manual verification.
```

### Acceptance Criteria
- Diarization is off by default — existing behavior unchanged.
- When enabled, every segment gets a `speaker_id`.
- At least 2 distinct speakers detected in the test fixture.
- Graceful error if `pyannote.audio` not installed (clear message: "Install diarization extras: pip install transcribe-cli[diarization]").

---

## WO-3: Speaker Labels in SRT Output

**File**: `src/transcribe_cli/output/formatters.py`

### Changes

1. Modify `format_as_srt()` to prepend speaker label when `segment.speaker_id` is not None:
   ```
   1
   00:00:00,000 --> 00:00:03,500
   [SPEAKER_00] Welcome to the tutorial.

   2
   00:00:03,800 --> 00:00:07,200
   [SPEAKER_01] Thanks for having me.
   ```
2. Only add labels when at least one segment has a `speaker_id` (don't pollute non-diarized output).

### Tests — add to `tests/unit/test_formatters.py`

```
test_srt_with_speaker_labels
    Create result with 2 segments, different speaker_ids.
    Assert SRT output contains "[SPEAKER_00]" and "[SPEAKER_01]".
    Assert SRT still parseable by srt.parse().

test_srt_no_speaker_labels_when_none
    Create result with segments where speaker_id=None.
    Assert SRT output does NOT contain "[SPEAKER" anywhere.

test_srt_mixed_speaker_and_none
    Create result: segment 1 has speaker_id, segment 2 has None.
    Assert segment 1 line contains "[SPEAKER_00]".
    Assert segment 2 line does NOT contain "[".

test_srt_speaker_labels_preserve_timestamps
    Parse SRT output with speaker labels.
    Assert timestamps still correct (labels don't corrupt timing).

test_srt_speaker_label_format
    Assert label format is exactly "[SPEAKER_XX] " prefix before text.
```

### Acceptance Criteria
- Existing SRT tests all still pass (no speaker labels unless speaker_id present).
- Speaker labels appear inline with subtitle text, parseable by standard SRT players.

---

## WO-4: VTT Output Format with Speaker Support

**File**: `src/transcribe_cli/output/formatters.py`

### Changes

1. Add `format_as_vtt(result: TranscriptionResult) -> str`:
   - Output `WEBVTT` header.
   - Each segment as `HH:MM:SS.mmm --> HH:MM:SS.mmm` with text body.
   - When `speaker_id` present, use `<v SPEAKER_XX>text</v>` voice tags (WebVTT standard for speaker identification).
2. Register `"vtt"` in `format_transcript()` dispatcher.
3. Update `get_output_extension()` for `"vtt"`.

### Tests — add to `tests/unit/test_formatters.py`

```
test_vtt_header
    Assert output starts with "WEBVTT\n\n".

test_vtt_single_segment
    Create result with 1 segment.
    Assert valid VTT: timestamp line with "-->", text line.

test_vtt_multiple_segments
    Create result with 3 segments.
    Assert 3 cue blocks present.

test_vtt_timestamps_format
    Segment at 65.5s - 68.123s.
    Assert "00:01:05.500 --> 00:01:08.123" in output.

test_vtt_with_speaker_voice_tags
    Segment with speaker_id="SPEAKER_00".
    Assert "<v SPEAKER_00>" in output.

test_vtt_no_voice_tags_when_no_speakers
    Segments without speaker_id.
    Assert "<v" not in output.

test_vtt_format_dispatch
    format_transcript(result, "vtt") returns VTT output.

test_vtt_extension
    get_output_extension("vtt") == ".vtt"

test_save_vtt_file (tmp_path)
    save_formatted_transcript(result, path, "vtt") creates file.
    File content starts with "WEBVTT".
```

### Acceptance Criteria
- VTT output validates against WebVTT spec (WEBVTT header, correct timestamp format `HH:MM:SS.mmm`).
- Voice tags used for speaker identification per W3C WebVTT spec.
- Playable in HTML5 `<track>` element.

---

## WO-5: JSON Output Format with Full Metadata

**File**: `src/transcribe_cli/output/formatters.py`

### Changes

1. Add `format_as_json(result: TranscriptionResult) -> str`:
   ```json
   {
     "input_file": "meeting.mp3",
     "language": "en",
     "duration": 125.4,
     "speakers": ["SPEAKER_00", "SPEAKER_01"],
     "word_count": 342,
     "segments": [
       {
         "id": 0,
         "start": 0.0,
         "end": 3.5,
         "text": "Welcome to the tutorial.",
         "speaker": "SPEAKER_00",
         "words": [
           {"word": "Welcome", "start": 0.0, "end": 0.4},
           {"word": "to", "start": 0.4, "end": 0.5},
           ...
         ]
       }
     ]
   }
   ```
2. Omit `speaker` key when null. Omit `words` array when empty. (Clean output for non-diarized, non-word-level runs.)
3. Register `"json"` in `format_transcript()` dispatcher.
4. Update `get_output_extension()`.

### Tests — add to `tests/unit/test_formatters.py`

```
test_json_valid_parse
    Output of format_as_json() is valid JSON (json.loads succeeds).

test_json_top_level_fields
    Assert keys: input_file, language, duration, word_count, segments.

test_json_segments_structure
    Each segment has id, start, end, text.

test_json_speaker_included_when_present
    Segment with speaker_id -> "speaker" key in JSON.

test_json_speaker_omitted_when_none
    Segment without speaker_id -> "speaker" key absent.

test_json_words_included_when_present
    Segment with words -> "words" array in JSON.

test_json_words_omitted_when_empty
    Segment without words -> "words" key absent.

test_json_speakers_list_at_top
    Result with speakers=["SPEAKER_00","SPEAKER_01"].
    Assert JSON top-level "speakers" matches.

test_json_format_dispatch
    format_transcript(result, "json") returns valid JSON.

test_json_extension
    get_output_extension("json") == ".json"

test_save_json_file (tmp_path)
    save_formatted_transcript(result, path, "json") creates valid JSON file.
```

### Acceptance Criteria
- Output is valid, pretty-printed JSON (indent=2).
- Schema is self-documenting — no external schema file needed.
- Null/empty optional fields omitted (not included as null).

---

## WO-6: Word-Level Timestamps

**File**: `src/transcribe_cli/core/transcriber.py`

### Changes

1. Modify `_transcribe_audio_file()` to pass `timestamp_granularities=["segment", "word"]` to the Whisper API when word-level timestamps are requested.
2. Modify `_parse_segments()` to extract word-level timestamps from the API response `words` array and populate `segment.words`.
3. Add `word_timestamps: bool = False` parameter to `transcribe_file()`.

### Whisper API Response Shape (with word timestamps)

```json
{
  "text": "Hello world",
  "segments": [...],
  "words": [
    {"word": "Hello", "start": 0.0, "end": 0.42},
    {"word": "world", "start": 0.42, "end": 0.84}
  ]
}
```

Words need to be matched to segments by time overlap.

### Tests — `tests/unit/test_word_timestamps.py` (new file)

```
test_parse_words_from_response
    Mock API response with "words" array.
    Assert _parse_segments returns segments with populated .words.

test_words_assigned_to_correct_segments
    Segment 1: 0-5s, Segment 2: 5-10s.
    Words at 1s, 3s, 6s, 8s.
    Assert segment 1 has 2 words, segment 2 has 2 words.

test_word_timestamps_accuracy
    Mock word with start=1.23, end=1.67.
    Assert WordTimestamp.start == 1.23, .end == 1.67.

test_no_words_when_disabled
    Call with word_timestamps=False (default).
    Assert all segments have empty .words lists.

test_words_empty_when_api_omits
    API response has segments but no "words" key.
    Assert segments created with empty .words (no crash).
```

### Integration Test — `tests/integration/test_word_timestamps_e2e.py`

```
test_word_timestamps_real_api (requires API key + fixture)
    transcribe_file("tests/fixtures/multi-speaker.mp3", word_timestamps=True).
    Assert at least one segment has len(words) > 0.
    Assert every word has start <= end.
    Assert words are chronologically ordered within each segment.
```

### Acceptance Criteria
- Word timestamps off by default (no API behavior change).
- When enabled, words array populated on each segment.
- Each word's time range falls within its parent segment's time range.

---

## WO-7: CLI and Config Options for Diarization and Word Timestamps

**Files**: `src/transcribe_cli/cli/main.py`, `src/transcribe_cli/config/settings.py`

### Changes

1. **CLI flags** (on `transcribe` and `batch` commands):
   - `--diarize / --no-diarize` (default: no-diarize) — enable speaker diarization
   - `--word-timestamps / --no-word-timestamps` (default: no) — enable word-level timestamps
   - `--format` updated to accept `"txt"`, `"srt"`, `"vtt"`, `"json"`

2. **Settings model**:
   - Add `diarize: bool = False`
   - Add `word_timestamps: bool = False`
   - Update `output_format: Literal["txt", "srt", "vtt", "json"] = "txt"`

3. **Config file template** (update `create_default_config`):
   ```toml
   [output]
   format = "txt"  # txt, srt, vtt, json

   [processing]
   diarize = false
   word_timestamps = false
   ```

4. **Environment variables**:
   - `TRANSCRIBE_DIARIZE=true/false`
   - `TRANSCRIBE_WORD_TIMESTAMPS=true/false`

5. **Wire through**: `transcribe` and `batch` commands pass `diarize` and `word_timestamps` to `transcribe_file()`.

### Tests — add to `tests/unit/test_config.py`

```
test_settings_diarize_default_false
    Settings() has diarize == False.

test_settings_diarize_from_env
    Set TRANSCRIBE_DIARIZE=true.
    Assert Settings().diarize == True.

test_settings_word_timestamps_default_false
    Settings() has word_timestamps == False.

test_settings_format_accepts_vtt
    Settings(output_format="vtt") succeeds.

test_settings_format_accepts_json
    Settings(output_format="json") succeeds.

test_default_config_includes_diarize
    create_default_config() output contains "diarize".
```

### CLI Tests — add to `tests/integration/test_cli.py`

```
test_cli_diarize_flag_accepted
    Invoke app with ["transcribe", "file.mp3", "--diarize"].
    Assert no "unknown option" error (flag is recognized).

test_cli_word_timestamps_flag_accepted
    Invoke app with ["transcribe", "file.mp3", "--word-timestamps"].
    Assert flag recognized.

test_cli_format_vtt_accepted
    Invoke app with ["transcribe", "file.mp3", "--format", "vtt"].
    Assert format validated without error.

test_cli_format_json_accepted
    Invoke app with ["transcribe", "file.mp3", "--format", "json"].
    Assert format validated without error.

test_cli_diarize_without_extras_shows_install_message
    When pyannote.audio not installed, --diarize flag.
    Assert error message contains "pip install transcribe-cli[diarization]".

test_batch_diarize_flag_accepted
    Invoke batch with ["batch", "./dir", "--diarize"].
    Assert flag recognized.
```

### Acceptance Criteria
- All new flags have `--no-*` counterparts (Typer boolean flags).
- Config file, env vars, and CLI flags all work with proper precedence.
- Format validation rejects unknown formats.
- Missing optional dependency gives actionable install instructions.

---

## WO-8: Batch Processing with Diarization

**File**: `src/transcribe_cli/core/batch.py`

### Changes

1. Add `diarize: bool = False` and `word_timestamps: bool = False` parameters to:
   - `_process_file_async()`
   - `process_batch_async()`
   - `process_batch()`
   - `process_directory()`
2. Pass through to `transcribe_file()`.
3. Update `cli/main.py` `batch` command to pass these flags.

### Tests — add to `tests/unit/test_batch.py`

```
test_batch_passes_diarize_to_transcribe (mock transcribe_file)
    Call process_batch(files, diarize=True).
    Assert transcribe_file was called with diarize=True for each file.

test_batch_passes_word_timestamps (mock transcribe_file)
    Call process_batch(files, word_timestamps=True).
    Assert transcribe_file was called with word_timestamps=True.

test_batch_default_no_diarize (mock transcribe_file)
    Call process_batch(files).
    Assert transcribe_file was called with diarize=False.

test_batch_diarize_with_srt_format (mock)
    process_batch(files, output_format="srt", diarize=True).
    Assert output files contain speaker labels.

test_batch_diarize_with_json_format (mock)
    process_batch(files, output_format="json", diarize=True).
    Assert JSON output contains speaker field.
```

### Integration Test

```
test_batch_diarize_directory (requires fixture files + API key)
    Place multi-speaker.mp3 in tmp directory.
    process_directory(dir, diarize=True, output_format="json").
    Assert JSON output has speakers list with >= 2 entries.
```

### Acceptance Criteria
- Batch processing with diarization uses same concurrency model (semaphore).
- Each file independently diarized (no cross-file speaker matching).
- Progress callback still works with diarization enabled.

---

## Test Fixture Requirements

**File needed**: `tests/fixtures/multi-speaker.mp3`

Requirements for the test audio:
- **Duration**: 2-5 minutes
- **Speakers**: Minimum 2 distinct speakers, ideally 3
- **Turn-taking**: Clear speaker alternation (not overlapping)
- **Content**: Conversational (each speaker says at least 3-4 sentences)
- **Audio quality**: Clean recording, minimal background noise
- **Language**: English

This file is used by integration tests in WO-2, WO-6, and WO-8. Unit tests use mocked data and do not need it.

---

## Implementation Order

| Phase | Work Orders | Estimated Effort |
|-------|-------------|-----------------|
| **1 - Foundation** | WO-1 (Data Model) | Small |
| **2 - Core Engine** | WO-6 (Word Timestamps), WO-2 (Diarization) — parallel | Medium each |
| **3 - Output Formats** | WO-3 (SRT Labels), WO-4 (VTT), WO-5 (JSON) — parallel | Small each |
| **4 - User Interface** | WO-7 (CLI/Config) | Medium |
| **5 - Integration** | WO-8 (Batch) | Small |

Phase 1 must complete first. Phases 2's two items can run in parallel. Phase 3 depends on Phase 2. Phases 4-5 depend on all prior.

---

## Running the Test Suite

```bash
# Unit tests only (no API key or fixture needed)
pytest tests/unit/ -v

# Integration tests (requires OPENAI_API_KEY + test fixture)
pytest tests/integration/ -v -k "diarization or word_timestamp"

# Full suite
pytest -v

# Specific work order validation
pytest tests/unit/test_models.py -v                    # WO-1
pytest tests/unit/test_diarization.py -v               # WO-2
pytest tests/unit/test_formatters.py -v -k "speaker"   # WO-3
pytest tests/unit/test_formatters.py -v -k "vtt"       # WO-4
pytest tests/unit/test_formatters.py -v -k "json"      # WO-5
pytest tests/unit/test_word_timestamps.py -v            # WO-6
pytest tests/unit/test_config.py -v -k "diarize"       # WO-7
pytest tests/unit/test_batch.py -v -k "diarize"        # WO-8
```
