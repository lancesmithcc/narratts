"""TTS engine wrapper around Qwen3-TTS models.

Lazy-loads models and caches one at a time. Thread-safe with a lock so
concurrent requests serialize model swaps.
"""
from __future__ import annotations

import copy
import enum
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from .config import settings

logger = logging.getLogger("tts.engine")


class ModelKey(str, enum.Enum):
    BASE_0_6B = "base-0.6b"
    BASE_1_7B = "base-1.7b"
    CUSTOMVOICE_0_6B = "customvoice-0.6b"
    CUSTOMVOICE_1_7B = "customvoice-1.7b"
    VOICEDESIGN_1_7B = "voicedesign-1.7b"


HF_MODEL_IDS: dict[ModelKey, str] = {
    ModelKey.BASE_0_6B: "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    ModelKey.BASE_1_7B: "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    ModelKey.CUSTOMVOICE_0_6B: "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
    ModelKey.CUSTOMVOICE_1_7B: "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    ModelKey.VOICEDESIGN_1_7B: "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
}

# Models that support each capability.
SUPPORTED = {
    "voice_clone": {ModelKey.BASE_0_6B, ModelKey.BASE_1_7B},
    "voice_design": {ModelKey.VOICEDESIGN_1_7B},
    "custom_voice": {ModelKey.CUSTOMVOICE_0_6B, ModelKey.CUSTOMVOICE_1_7B},
}


@dataclass
class AudioResult:
    """Result of a TTS generation."""
    wav: Any                 # numpy float32 mono array
    sample_rate: int
    duration_s: float
    model: str
    text_chars: int


def _device_settings() -> tuple[str, Any, str]:
    """Pick the best device, dtype, and attention impl for this machine."""
    import torch

    if torch.cuda.is_available():
        return "cuda:0", torch.bfloat16, "flash_attention_2"
    if torch.backends.mps.is_available():
        return "mps", torch.float32, "sdpa"
    return "cpu", torch.float32, "sdpa"


class TTSEngine:
    """Lazy-loaded model cache. One model loaded at a time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded_key: ModelKey | None = None
        self._loaded_model: Any | None = None
        self._qwen_cls: Any | None = None

    # ── Lifecycle ────────────────────────────────────────────────
    def warm(self, key: ModelKey | None = None) -> None:
        """Pre-load a model so the first request is fast."""
        if key is None:
            key = ModelKey(settings.default_model)
        self._load(key)

    def unload(self) -> None:
        import torch

        with self._lock:
            self._loaded_model = None
            self._loaded_key = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def status(self) -> dict:
        with self._lock:
            loaded = self._loaded_key.value if self._loaded_key else None
        device, dtype, attn = _device_settings()
        return {
            "loaded_model": loaded,
            "available_models": [k.value for k in ModelKey],
            "device": device,
            "dtype": str(dtype).replace("torch.", ""),
            "attention": attn,
        }

    def _load(self, key: ModelKey) -> Any:
        with self._lock:
            if self._loaded_key == key and self._loaded_model is not None:
                return self._loaded_model
            t0 = time.time()
            if self._loaded_key != key:
                logger.info("Loading model %s ...", key.value)
                # Lazy import to keep startup light.
                if self._qwen_cls is None:
                    from qwen_tts import Qwen3TTSModel
                    self._qwen_cls = Qwen3TTSModel
                import torch

                device, dtype, attn = _device_settings()
                kwargs: dict[str, Any] = dict(
                    device_map=device,
                    dtype=dtype,
                    attn_implementation=attn,
                )
                if settings.hf_token:
                    kwargs["token"] = settings.hf_token
                self._loaded_model = self._qwen_cls.from_pretrained(
                    HF_MODEL_IDS[key], **kwargs
                )
                self._loaded_key = key
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                logger.info("Loaded %s in %.1fs", key.value, time.time() - t0)
            return self._loaded_model

    def _resolve_model(self, requested: str | None, capability: str) -> ModelKey:
        key = ModelKey(requested) if requested else ModelKey(settings.default_model)
        if key not in SUPPORTED[capability]:
            supported = ", ".join(k.value for k in SUPPORTED[capability])
            raise ValueError(
                f"Model '{key.value}' does not support {capability}. "
                f"Use one of: {supported}"
            )
        return key

    # ── Metadata ─────────────────────────────────────────────────
    def supported_languages(self, model: str | None = None) -> list[str]:
        """Return languages for the given model. Falls back to the default."""
        key = ModelKey(model) if model else ModelKey(settings.default_model)
        m = self._load(key)
        langs = m.get_supported_languages()
        if langs:
            return langs
        return [
            "English", "Chinese", "Japanese", "Korean",
            "German", "French", "Russian", "Portuguese",
            "Spanish", "Italian",
        ]

    def supported_speakers(self, model: str | None = None) -> list[str]:
        key = ModelKey(model) if model else ModelKey.CUSTOMVOICE_0_6B
        m = self._load(key)
        speakers = m.get_supported_speakers() or []
        return speakers

    # ── Generation ───────────────────────────────────────────────
    def voice_clone(
        self,
        text: str,
        ref_audio: list[str],
        language: str = "English",
        ref_text: list[str] | None = None,
        x_vector_only: bool = True,
        merge_refs: bool = True,
        model: str | None = None,
    ) -> AudioResult:
        import torch

        key = self._resolve_model(model, "voice_clone")
        if len(ref_audio) > settings.max_refs_per_request:
            raise ValueError(f"Too many reference audio files: {len(ref_audio)}")
        m = self._load(key)

        if (
            len(ref_audio) > 1
            and x_vector_only
            and merge_refs
        ):
            # Average speaker embeddings across references for richer voice.
            prompts = m.create_voice_clone_prompt(
                ref_audio=ref_audio,
                x_vector_only_mode=[True] * len(ref_audio),
            )
            embeddings = [p.ref_spk_embedding for p in prompts]
            avg_emb = torch.stack(embeddings).mean(dim=0)
            combined = copy.copy(prompts[0])
            combined.ref_spk_embedding = avg_emb
            wavs, sr = m.generate_voice_clone(
                text=text, language=language,
                voice_clone_prompt=[combined],
                non_streaming_mode=True,
            )
        else:
            wavs, sr = m.generate_voice_clone(
                text=text, language=language,
                ref_audio=ref_audio[0] if len(ref_audio) == 1 else ref_audio,
                ref_text=ref_text[0] if (ref_text and len(ref_text) == 1) else ref_text,
                x_vector_only_mode=x_vector_only,
                non_streaming_mode=True,
            )
        return self._wrap(wavs[0], sr, key.value, text)

    def voice_design(
        self,
        text: str,
        instruct: str,
        language: str = "English",
        model: str | None = None,
    ) -> AudioResult:
        key = self._resolve_model(model, "voice_design")
        m = self._load(key)
        wavs, sr = m.generate_voice_design(
            text=text, instruct=instruct, language=language, non_streaming_mode=True,
        )
        return self._wrap(wavs[0], sr, key.value, text)

    def custom_voice(
        self,
        text: str,
        speaker: str,
        language: str = "English",
        instruct: str | None = None,
        model: str | None = None,
    ) -> AudioResult:
        key = self._resolve_model(model, "custom_voice")
        m = self._load(key)
        wavs, sr = m.generate_custom_voice(
            text=text, speaker=speaker, language=language,
            instruct=instruct, non_streaming_mode=True,
        )
        return self._wrap(wavs[0], sr, key.value, text)

    # ── Helpers ───────────────────────────────────────────────────
    def _wrap(self, wav: Any, sr: int, model: str, text: str) -> AudioResult:
        import numpy as np

        # Ensure float32 mono.
        if wav.dtype != np.float32:
            wav = wav.astype(np.float32)
        if wav.ndim > 1:
            wav = wav.mean(axis=1)
        return AudioResult(
            wav=wav,
            sample_rate=int(sr),
            duration_s=float(len(wav) / sr),
            model=model,
            text_chars=len(text),
        )


# Module-level singleton.
engine = TTSEngine()


def save_wav(result: AudioResult, path) -> int:
    """Write AudioResult to a WAV file. Returns bytes written."""
    import soundfile as sf

    sf.write(str(path), result.wav, result.sample_rate, subtype="PCM_16")
    import os
    return os.path.getsize(str(path))
