"""Reference voice storage.

Voices are stored on disk in `voices/<voice_id>/`:
  - voice.wav       the audio file
  - meta.json       id, name, language, transcript, timestamps

The voice_id is a short random slug. Uploaded files keep their original
format (wav, mp3, flac, ogg, m4a).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from .config import settings

logger = logging.getLogger("tts.storage")

# Allowed audio extensions.
ALLOWED_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".opus"}

SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    s = SLUG_RE.sub("-", name.lower()).strip("-")
    return s or "voice"


@dataclass
class VoiceMeta:
    voice_id: str
    name: str
    language: str = "English"
    transcript: Optional[str] = None
    filename: str = "voice.wav"
    size_bytes: int = 0
    duration_s: float = 0.0
    created_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)

    @property
    def path(self) -> Path:
        return settings.voices_dir / self.voice_id / self.filename

    @property
    def folder(self) -> Path:
        return settings.voices_dir / self.voice_id


class VoiceStore:
    """CRUD for uploaded reference voices."""

    def __init__(self) -> None:
        settings.voices_dir.mkdir(exist_ok=True)

    # ── Create ─────────────────────────────────────────────────────
    def create(
        self,
        file_bytes: bytes,
        filename: str,
        name: str | None = None,
        language: str = "English",
        transcript: str | None = None,
        tags: list[str] | None = None,
    ) -> VoiceMeta:
        if len(file_bytes) > settings.max_voice_bytes:
            raise ValueError(
                f"Voice file too large: {len(file_bytes)} bytes "
                f"(max {settings.max_voice_bytes})"
            )
        ext = Path(filename).suffix.lower() or ".wav"
        if ext not in ALLOWED_EXTS:
            raise ValueError(
                f"Unsupported audio format '{ext}'. Allowed: {sorted(ALLOWED_EXTS)}"
            )
        # Build a stable id from content hash + name slug.
        digest = hashlib.sha256(file_bytes).hexdigest()[:10]
        base_slug = slugify(name or Path(filename).stem or "voice")
        voice_id = f"{base_slug}-{digest}"
        folder = settings.voices_dir / voice_id
        if folder.exists():
            raise FileExistsError(f"Voice '{voice_id}' already exists")

        folder.mkdir(parents=True)
        out_name = f"voice{ext}"
        out_path = folder / out_name
        out_path.write_bytes(file_bytes)

        duration_s = self._probe_duration(out_path)
        meta = VoiceMeta(
            voice_id=voice_id,
            name=name or base_slug,
            language=language,
            transcript=transcript,
            filename=out_name,
            size_bytes=len(file_bytes),
            duration_s=duration_s,
            tags=tags or [],
        )
        (folder / "meta.json").write_text(json.dumps(asdict(meta), indent=2))
        logger.info("Created voice %s (%d bytes, %.1fs)",
                    voice_id, meta.size_bytes, meta.duration_s)
        return meta

    # ── Read ───────────────────────────────────────────────────────
    def get(self, voice_id: str) -> Optional[VoiceMeta]:
        meta_path = settings.voices_dir / voice_id / "meta.json"
        if not meta_path.exists():
            return None
        data = json.loads(meta_path.read_text())
        return VoiceMeta(**data)

    def require(self, voice_id: str) -> VoiceMeta:
        m = self.get(voice_id)
        if m is None:
            raise KeyError(f"Voice '{voice_id}' not found")
        return m

    def path_for(self, voice_id: str) -> Path:
        meta = self.require(voice_id)
        return meta.path

    def list_all(self) -> list[VoiceMeta]:
        out = []
        for d in sorted(settings.voices_dir.iterdir()):
            if not d.is_dir():
                continue
            meta = self.get(d.name)
            if meta is not None:
                out.append(meta)
        return out

    # ── Update ─────────────────────────────────────────────────────
    def update(
        self,
        voice_id: str,
        name: str | None = None,
        language: str | None = None,
        transcript: str | None = None,
        tags: list[str] | None = None,
    ) -> VoiceMeta:
        meta = self.require(voice_id)
        if name is not None:
            meta.name = name
        if language is not None:
            meta.language = language
        if transcript is not None:
            meta.transcript = transcript
        if tags is not None:
            meta.tags = tags
        (meta.folder / "meta.json").write_text(json.dumps(asdict(meta), indent=2))
        return meta

    # ── Delete ─────────────────────────────────────────────────────
    def delete(self, voice_id: str) -> bool:
        import shutil
        meta = self.get(voice_id)
        if meta is None:
            return False
        shutil.rmtree(meta.folder)
        logger.info("Deleted voice %s", voice_id)
        return True

    # ── Helpers ────────────────────────────────────────────────────
    def _probe_duration(self, path: Path) -> float:
        try:
            import soundfile as sf
            with sf.SoundFile(str(path)) as f:
                return float(len(f) / f.samplerate)
        except Exception:
            return 0.0


store = VoiceStore()