# transcribe-cli

**Local audio/video transcription with speaker diarization. No API keys. No cloud. One command.**

## Quickstart

```bash
curl -sSL https://raw.githubusercontent.com/robit-man/transcribe-cli/main/install.sh | bash
```

Then:

```bash
transcribe audio.mp3
transcribe meeting.wav --model medium --diarize --format json
transcribe batch ./recordings --recursive --format srt
```

---

## Features

- **100% Local** — Runs on your machine via [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2). No API keys, no cloud, no data leaves your system.
- **Speaker Diarization** — Identify who said what with `--diarize` (via [pyannote.audio](https://github.com/pyannote/pyannote-audio))
- **Word-Level Timestamps** — Precise per-word timing with `--word-timestamps`
- **4 Output Formats** — `txt`, `srt` (with speaker labels), `vtt` (with W3C voice tags), `json` (full metadata)
- **Audio + Video** — MP3, WAV, FLAC, AAC, M4A, OGG, WMA, MP4, MKV, AVI, MOV, WebM, FLV
- **Batch Processing** — Process entire directories with configurable concurrency
- **5 Model Sizes** — `tiny`, `base`, `small`, `medium`, `large-v3` (auto-downloads on first use)
- **Auto Audio Extraction** — Videos are automatically handled via FFmpeg
- **Cross-Platform** — Linux and macOS

## Requirements

- Python 3.9+
- FFmpeg 4.0+
- ~1 GB disk (for base model; large-v3 needs ~3 GB)

The install script handles all dependencies automatically.

## Installation

### One-Line Install (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/robit-man/transcribe-cli/main/install.sh | bash
```

This will:
1. Install system dependencies (Python, FFmpeg, git) if missing
2. Clone the repository to `~/.local/share/transcribe-cli`
3. Create a Python virtual environment with all packages
4. Pre-download the default Whisper model (`base`)
5. Create `transcribe` and `transcribe-cli` commands in `~/.local/bin`
6. Add `~/.local/bin` to your PATH if needed

**Environment variables** (optional):
- `TRANSCRIBE_INSTALL_DIR` — Custom install location (default: `~/.local/share/transcribe-cli`)
- `TRANSCRIBE_MODEL` — Model to pre-download (default: `base`)

### Manual Install

```bash
git clone https://github.com/robit-man/transcribe-cli.git
cd transcribe-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### With Speaker Diarization

```bash
pip install -e ".[diarization]"
```

## Usage

### Transcribe a Single File

```bash
transcribe audio.mp3
transcribe video.mkv --format srt
transcribe recording.wav --output-dir ./transcripts
transcribe lecture.mp3 --model medium --language en
```

### Speaker Diarization

```bash
transcribe meeting.wav --diarize --format srt
transcribe interview.mp3 --diarize --format json
transcribe podcast.mp3 --diarize --word-timestamps --format vtt
```

### Batch Processing

```bash
transcribe batch ./recordings
transcribe batch ./videos --format srt --concurrency 3
transcribe batch ./media --recursive --dry-run
transcribe batch ./meetings --model medium --diarize --format json
```

### Audio Extraction

```bash
transcribe extract video.mkv
transcribe extract video.mp4 --output audio.mp3
transcribe extract video.avi --format wav
```

### Configuration

```bash
transcribe config --show        # Show current settings
transcribe config --init        # Create transcribe.toml in current directory
transcribe config --locations   # Show config file search paths
```

### Dependency Check

```bash
transcribe setup --check
```

## CLI Reference

### `transcribe <file> [OPTIONS]`

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output-dir` | `-o` | Output directory | Current dir |
| `--format` | `-f` | Output format: `txt`, `srt`, `vtt`, `json` | `txt` |
| `--language` | `-l` | Language code or `auto` | `auto` |
| `--model` | `-m` | Model: `tiny`, `base`, `small`, `medium`, `large-v3` | `base` |
| `--diarize` | | Enable speaker diarization | Off |
| `--word-timestamps` | | Enable word-level timestamps | Off |
| `--verbose` | | Verbose output | Off |

### `transcribe batch <directory> [OPTIONS]`

All options from `transcribe` plus:

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--concurrency` | `-c` | Max concurrent jobs (1-20) | `5` |
| `--recursive` | `-r` | Scan subdirectories | Off |
| `--dry-run` | | Preview files without processing | Off |

### `transcribe extract <file> [OPTIONS]`

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output` | `-o` | Output file path | Auto-generated |
| `--format` | `-f` | Audio format: `mp3`, `wav` | `mp3` |

## Output Formats

### TXT — Plain text
```
Hello, welcome to the meeting. Today we'll discuss the quarterly results.
```

### SRT — SubRip subtitles (with speaker labels when diarized)
```
1
00:00:00,000 --> 00:00:03,500
[SPEAKER_00] Hello, welcome to the meeting.

2
00:00:03,500 --> 00:00:07,200
[SPEAKER_01] Thanks for having me.
```

### VTT — WebVTT (with W3C voice tags when diarized)
```
WEBVTT

00:00:00.000 --> 00:00:03.500
<v SPEAKER_00>Hello, welcome to the meeting.</v>

00:00:03.500 --> 00:00:07.200
<v SPEAKER_01>Thanks for having me.</v>
```

### JSON — Full metadata
```json
{
  "text": "Hello, welcome to the meeting...",
  "language": "en",
  "duration": 120.5,
  "speakers": ["SPEAKER_00", "SPEAKER_01"],
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 3.5,
      "text": "Hello, welcome to the meeting.",
      "speaker": "SPEAKER_00",
      "words": [
        {"word": "Hello,", "start": 0.1, "end": 0.5},
        {"word": "welcome", "start": 0.6, "end": 1.0}
      ]
    }
  ]
}
```

## Configuration File

Create with `transcribe config --init`:

```toml
[output]
format = "txt"

[processing]
concurrency = 5
language = "auto"
recursive = false

[model]
size = "base"
device = "auto"
compute_type = "auto"

[features]
diarize = false
word_timestamps = false
```

Config files are searched in order:
1. `./transcribe.toml`
2. `./.transcriberc`
3. `~/.config/transcribe/config.toml`
4. `~/.transcriberc`

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TRANSCRIBE_MODEL_SIZE` | Whisper model size | `base` |
| `TRANSCRIBE_DEVICE` | Compute device (`auto`/`cpu`/`cuda`) | `auto` |
| `TRANSCRIBE_COMPUTE_TYPE` | Compute type (`auto`/`int8`/`float16`/`float32`) | `auto` |
| `TRANSCRIBE_CONCURRENCY` | Max concurrent batch jobs | `5` |
| `TRANSCRIBE_LANGUAGE` | Default language | `auto` |
| `TRANSCRIBE_DIARIZE` | Enable diarization by default | `false` |
| `TRANSCRIBE_WORD_TIMESTAMPS` | Enable word timestamps by default | `false` |

## Model Sizes

| Model | Size | English | Multilingual | Speed |
|-------|------|---------|-------------|-------|
| `tiny` | ~75 MB | Good | Fair | Fastest |
| `base` | ~150 MB | Better | Good | Fast |
| `small` | ~500 MB | Great | Great | Moderate |
| `medium` | ~1.5 GB | Excellent | Excellent | Slower |
| `large-v3` | ~3 GB | Best | Best | Slowest |

Models are auto-downloaded on first use and cached locally.

## Development

```bash
git clone https://github.com/robit-man/transcribe-cli.git
cd transcribe-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Run tests without coverage
pytest tests/unit/ -v --no-cov
```

## Uninstall

```bash
rm -rf ~/.local/share/transcribe-cli
rm -f ~/.local/bin/transcribe ~/.local/bin/transcribe-cli
```

## License

MIT

## Acknowledgments

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — CTranslate2 Whisper implementation
- [pyannote.audio](https://github.com/pyannote/pyannote-audio) — Speaker diarization
- [FFmpeg](https://ffmpeg.org/) — Audio/video processing
- [Typer](https://typer.tiangolo.com/) — CLI framework
- [Rich](https://github.com/Textualize/rich) — Terminal formatting
