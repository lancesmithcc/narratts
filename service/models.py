"""Pydantic request/response schemas."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Health / metadata ───────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: Literal["ok", "loading"]
    status_endpoint: str = "/health"
    api_version: str = "1"
    loaded_model: Optional[str] = None
    available_models: list[str]
    device: str
    dtype: str
    attention: str


class LanguagesResponse(BaseModel):
    languages: list[str]
    model: str


class SpeakersResponse(BaseModel):
    speakers: list[str]
    model: str


class ModelsResponse(BaseModel):
    models: list[str]
    capabilities: dict[str, list[str]]


# ── Voices ─────────────────────────────────────────────────────────
class VoiceInfo(BaseModel):
    voice_id: str
    name: str
    language: str
    has_transcript: bool
    filename: str
    size_bytes: int
    duration_s: float
    created_at: float
    tags: list[str] = Field(default_factory=list)


class VoicesResponse(BaseModel):
    voices: list[VoiceInfo]


class VoiceUploadRequest(BaseModel):
    name: Optional[str] = None
    language: str = "English"
    transcript: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class VoiceUpdateRequest(BaseModel):
    name: Optional[str] = None
    language: Optional[str] = None
    transcript: Optional[str] = None
    tags: Optional[list[str]] = None


# ── TTS requests ───────────────────────────────────────────────────
class VoiceCloneRequest(BaseModel):
    text: str = Field(..., max_length=2000, description="Text to speak")
    language: str = Field("English")
    voice_ids: list[str] = Field(
        ..., min_length=1, max_length=5,
        description="1-5 voice IDs to clone from. Embeddings are averaged.",
    )
    transcripts: Optional[list[str]] = Field(
        None,
        description="Optional transcript for each voice_id (improves accuracy). Same order as voice_ids.",
    )
    x_vector_only: bool = Field(
        True, description="Extract voice embedding only — no transcript needed",
    )
    model: Optional[str] = Field(
        None, description="base-0.6b or base-1.7b (default: configured default)",
    )
    output_format: Literal["wav_base64", "url"] = "wav_base64"


class VoiceDesignRequest(BaseModel):
    text: str = Field(..., max_length=2000)
    instruct: str = Field(
        ..., min_length=5, max_length=500,
        description="Voice description e.g. 'A middle-aged Scottish man with a deep gravelly voice'",
    )
    language: str = "English"
    model: Optional[str] = "voicedesign-1.7b"
    output_format: Literal["wav_base64", "url"] = "wav_base64"


class CustomVoiceRequest(BaseModel):
    text: str = Field(..., max_length=2000)
    speaker: str = Field(..., description="Built-in speaker name")
    language: str = "English"
    instruct: Optional[str] = Field(
        None, description="Optional style/voice instruction",
    )
    model: Optional[str] = "customvoice-0.6b"
    output_format: Literal["wav_base64", "url"] = "wav_base64"


# ── Responses ───────────────────────────────────────────────────────
class AudioResponse(BaseModel):
    audio_base64: Optional[str] = None
    url: Optional[str] = None
    sample_rate: int
    duration_s: float
    format: str = "wav"
    model: str
    text_chars: int


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


# ── Demucs ──────────────────────────────────────────────────────────
class IsolateVocalsRequest(BaseModel):
    voice_id: str = Field(..., description="Voice ID to isolate vocals from")


class IsolateVocalsResponse(BaseModel):
    voice_id: str
    vocals_voice_id: str
    duration_s: float
    size_bytes: int
