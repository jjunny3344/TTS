import os
from dataclasses import dataclass, field
from pathlib import Path


def _opt_int(name: str) -> int | None:
    value = os.getenv(name)
    return int(value) if value else None


def _opt_path(name: str) -> Path | None:
    value = os.getenv(name)
    return Path(value) if value else None


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _default_model_dir() -> Path:
    # Model files bundled in the repo: models/<model name>
    return _opt_path("TTS_MODEL_DIR") or PROJECT_ROOT / "models" / os.getenv("TTS_MODEL", "supertonic-3")


@dataclass(frozen=True)
class Settings:
    # Model
    model: str = field(default_factory=lambda: os.getenv("TTS_MODEL", "supertonic-3"))
    model_dir: Path = field(default_factory=_default_model_dir)
    # Off by default: the model ships with the repo, so a missing file should fail fast, not hit the network
    auto_download: bool = field(
        default_factory=lambda: os.getenv("TTS_AUTO_DOWNLOAD", "false").lower() == "true"
    )
    intra_op_threads: int | None = field(default_factory=lambda: _opt_int("TTS_INTRA_OP_THREADS"))
    # Directory of extra voice-style JSON files (e.g. Voice Builder exports); file stem = voice name
    custom_voices_dir: Path | None = field(default_factory=lambda: _opt_path("TTS_CUSTOM_VOICES_DIR"))

    # Synthesis defaults
    default_voice: str = field(default_factory=lambda: os.getenv("TTS_DEFAULT_VOICE", "F1"))
    default_lang: str = field(default_factory=lambda: os.getenv("TTS_DEFAULT_LANG", "ko"))

    # Service limits
    max_text_chars: int = field(default_factory=lambda: int(os.getenv("TTS_MAX_TEXT_CHARS", "5000")))
    # Concurrent synthesis jobs. ONNX Runtime already uses all cores per job, so 1-2 is usually best.
    max_concurrency: int = field(default_factory=lambda: int(os.getenv("TTS_MAX_CONCURRENCY", "1")))

    # If set, requests must send "Authorization: Bearer <key>"
    api_key: str | None = field(default_factory=lambda: os.getenv("TTS_API_KEY") or None)
