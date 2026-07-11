"""Service configuration loaded from environment / .env file."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (parent of service/)
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


class Settings:
    """Service settings. Reads from env vars at import time."""

    # ── Auth ─────────────────────────────────────────────────────────
    # Comma-separated list of valid API keys. If empty, no auth (dev only).
    api_keys: set[str] = set(_split_csv(os.getenv("TTS_API_KEYS")))
    allow_unauthenticated: bool = _as_bool(os.getenv("TTS_ALLOW_UNAUTHENTICATED"))

    # ── Service ──────────────────────────────────────────────────────
    host: str = os.getenv("TTS_HOST", "127.0.0.1")
    port: int = int(os.getenv("TTS_PORT", "8765"))
    log_level: str = os.getenv("TTS_LOG_LEVEL", "info")
    cors_origins: list[str] = _split_csv(os.getenv("TTS_CORS_ORIGINS"))

    # ── Models / HuggingFace ─────────────────────────────────────────
    hf_token: str | None = os.getenv("HF_TOKEN") or None
    # Default model to keep warm on startup. Use "auto" for lazy.
    default_model: str = os.getenv("TTS_DEFAULT_MODEL", "base-1.7b")
    warm_on_start: bool = _as_bool(os.getenv("TTS_WARM_ON_START"), default=True)

    # ── Storage ──────────────────────────────────────────────────────
    data_dir: Path = Path(os.getenv("TTS_DATA_DIR", "~/.narratts")).expanduser().resolve()
    voices_dir: Path = data_dir / "voices"
    samples_dir: Path = data_dir / "samples"
    # Outputs go to a temp dir; clients download by ID.
    outputs_dir: Path = data_dir / "outputs"
    max_voice_bytes: int = int(os.getenv("TTS_MAX_VOICE_BYTES", "50000000"))  # 50MB
    # How long to keep generated outputs before cleanup (seconds).
    output_ttl_seconds: int = int(os.getenv("TTS_OUTPUT_TTL", "3600"))

    # ── Generation limits ─────────────────────────────────────────────
    max_text_chars: int = int(os.getenv("TTS_MAX_TEXT_CHARS", "2000"))
    max_refs_per_request: int = int(os.getenv("TTS_MAX_REFS", "5"))

    def ensure_dirs(self) -> None:
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.samples_dir.mkdir(parents=True, exist_ok=True)

    def validate_network_security(self) -> None:
        loopback = {"127.0.0.1", "localhost", "::1"}
        if not self.api_keys and self.host not in loopback and not self.allow_unauthenticated:
            raise RuntimeError(
                "Refusing unauthenticated non-loopback bind. Set TTS_API_KEYS or explicitly set "
                "TTS_ALLOW_UNAUTHENTICATED=true."
            )


settings = Settings()
settings.ensure_dirs()
