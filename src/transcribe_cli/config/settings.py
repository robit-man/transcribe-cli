"""Configuration settings for transcribe-cli.

Implements ADR-005: Configuration Management Strategy
- Hierarchical config: CLI args -> env vars -> config file -> defaults
- pydantic BaseSettings with TRANSCRIBE_ env prefix
"""

import tomllib
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Supported output formats
OutputFormat = Literal["txt", "srt", "vtt", "json"]

# Config file locations (checked in order)
CONFIG_LOCATIONS = [
    Path.cwd() / "transcribe.toml",
    Path.cwd() / ".transcriberc",
    Path.home() / ".config" / "transcribe" / "config.toml",
    Path.home() / ".transcriberc",
]


def find_config_file() -> Optional[Path]:
    """Find the first existing config file.

    Returns:
        Path to config file if found, None otherwise.
    """
    for path in CONFIG_LOCATIONS:
        if path.exists() and path.is_file():
            return path
    return None


def load_config_file(path: Optional[Path] = None) -> dict[str, Any]:
    """Load configuration from TOML file.

    Args:
        path: Explicit path to config file (optional).

    Returns:
        Dictionary of configuration values.
    """
    config_path = path or find_config_file()
    if not config_path:
        return {}

    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


class Settings(BaseSettings):
    """Application settings with hierarchical configuration.

    Priority (highest to lowest):
    1. CLI arguments (handled by Typer)
    2. Environment variables (TRANSCRIBE_ prefix)
    3. Config file (transcribe.toml or .transcriberc)
    4. Default values
    """

    model_config = SettingsConfigDict(
        env_prefix="TRANSCRIBE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Model settings
    model_size: str = Field(
        default="base",
        description="Whisper model size: tiny, base, small, medium, large-v3",
    )
    device: str = Field(
        default="auto",
        description="Compute device: auto, cpu, cuda",
    )
    compute_type: str = Field(
        default="auto",
        description="Precision mode: auto, float16, float32, int8",
    )

    # Output settings
    output_dir: Path = Path(".")
    output_format: OutputFormat = "txt"

    # Processing settings
    concurrency: int = 5
    language: str = "auto"
    chunk_size_minutes: int = 10
    recursive: bool = False
    diarize: bool = False
    word_timestamps: bool = False

    # Logging settings
    verbose: bool = False
    quiet: bool = False

    @field_validator("concurrency")
    @classmethod
    def validate_concurrency(cls, v: int) -> int:
        """Ensure concurrency is within reasonable bounds."""
        if v < 1:
            raise ValueError("Concurrency must be at least 1")
        if v > 20:
            raise ValueError("Concurrency cannot exceed 20")
        return v

    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, v: Path) -> Path:
        """Ensure output directory exists or can be created."""
        v = Path(v).resolve()
        if v.exists() and not v.is_dir():
            raise ValueError(f"Output path exists but is not a directory: {v}")
        return v

    @field_validator("model_size")
    @classmethod
    def validate_model_size(cls, v: str) -> str:
        """Ensure model size is a known variant."""
        valid = {"tiny", "base", "small", "medium", "large-v3", "large-v2", "large-v1", "large"}
        if v not in valid:
            raise ValueError(
                f"Unknown model size '{v}'. Valid options: {', '.join(sorted(valid))}"
            )
        return v

    @field_validator("device")
    @classmethod
    def validate_device(cls, v: str) -> str:
        """Ensure device is a supported value."""
        valid = {"auto", "cpu", "cuda"}
        if v not in valid:
            raise ValueError(f"Unknown device '{v}'. Valid options: auto, cpu, cuda")
        return v

    @field_validator("compute_type")
    @classmethod
    def validate_compute_type(cls, v: str) -> str:
        """Ensure compute_type is a supported value."""
        valid = {"auto", "float16", "float32", "int8", "int8_float16", "int8_float32"}
        if v not in valid:
            raise ValueError(
                f"Unknown compute_type '{v}'. Valid options: {', '.join(sorted(valid))}"
            )
        return v


def get_settings(config_path: Optional[Path] = None) -> Settings:
    """Load settings from environment and config file.

    Args:
        config_path: Explicit path to config file (optional).

    Returns:
        Settings: Validated application settings.

    Raises:
        ValidationError: If settings are invalid.
    """
    file_config = load_config_file(config_path)
    return Settings(**file_config)  # type: ignore[arg-type]


def get_config_locations() -> list[Path]:
    """Get list of config file locations checked.

    Returns:
        List of paths checked for config files.
    """
    return CONFIG_LOCATIONS.copy()


def create_default_config(path: Optional[Path] = None) -> Path:
    """Create a default config file with comments.

    Args:
        path: Where to create the config file (default: ./transcribe.toml).

    Returns:
        Path to created config file.
    """
    config_path = path or Path.cwd() / "transcribe.toml"

    content = '''# Transcribe CLI Configuration
# See: transcribe config --show

[model]
# Whisper model size: tiny, base, small, medium, large-v3
# Larger models are more accurate but slower and use more memory.
size = "base"

# Compute device: auto, cpu, cuda
device = "auto"

# Precision mode: auto, float16, float32, int8
compute_type = "auto"

[output]
# Output format: "txt", "srt", "vtt", or "json"
format = "txt"

# Default output directory (empty = same as input)
# dir = "./transcripts"

[processing]
# Maximum concurrent transcriptions (1-20)
concurrency = 5

# Language code or "auto" for detection
language = "auto"

# Recursively scan directories
recursive = false

# Enable speaker diarization (requires: pip install transcribe-cli[diarization])
diarize = false

# Enable word-level timestamps
word_timestamps = false

[logging]
# Enable verbose output
verbose = false
'''

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content)
    return config_path
