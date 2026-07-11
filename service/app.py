"""Qwen3-TTS API service.

Run:
    uvicorn service.app:app --host 0.0.0.0 --port 8765

Auth: Authorization: Bearer <TTS_API_KEY>
Docs: http://localhost:8765/docs  (Swagger UI)
       http://localhost:8765/redoc
       http://localhost:8765/llms.txt  (AI-friendly docs index)
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import shutil
import tempfile
import time
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from .config import settings
from .engine import SUPPORTED, ModelKey, engine, save_wav
from .models import (
    AudioResponse,
    CustomVoiceRequest,
    ErrorResponse,
    HealthResponse,
    IsolateVocalsRequest,
    IsolateVocalsResponse,
    LanguagesResponse,
    ModelsResponse,
    SpeakersResponse,
    VoiceCloneRequest,
    VoiceDesignRequest,
    VoiceInfo,
    VoicesResponse,
    VoiceUpdateRequest,
)
from .storage import store

# ── Logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("tts")


async def _expire_outputs() -> None:
    """Remove URL-based outputs after their configured lifetime."""
    while True:
        cutoff = time.time() - settings.output_ttl_seconds
        for path in settings.outputs_dir.glob("*.wav"):
            with suppress(OSError):
                if path.stat().st_mtime < cutoff:
                    path.unlink()
        await asyncio.sleep(min(60, max(5, settings.output_ttl_seconds)))


# ── Auth ─────────────────────────────────────────────────────────
auth_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    creds: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
) -> str:
    """Validate Bearer token against the configured API key set.

    If `settings.api_keys` is empty, auth is disabled (dev mode).
    """
    if not settings.api_keys:
        return "anonymous"
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Missing Bearer token. Send Authorization: Bearer <TTS_API_KEY>.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if creds.credentials not in settings.api_keys:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key.",
        )
    return creds.credentials


# ── Lifespan ─────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting TTS service on %s:%d", settings.host, settings.port)
    settings.validate_network_security()
    settings.ensure_dirs()
    # Warm default model in background so first request is fast.
    async def _warm():
        try:
            await asyncio.to_thread(engine.warm)
            log.info("Warmed default model %s", settings.default_model)
        except Exception as e:
            log.error("Failed to warm model: %s", e)
    cleanup_task = asyncio.create_task(_expire_outputs())
    if settings.warm_on_start:
        asyncio.create_task(_warm())
    yield
    cleanup_task.cancel()
    with suppress(asyncio.CancelledError):
        await cleanup_task
    log.info("Shutting down")
    engine.unload()


app = FastAPI(
    title="Qwen3-TTS API",
    version="1.0.0",
    description=(
        "Local Qwen3-TTS inference service. "
        "Supports voice cloning, voice design, custom voices, "
        "and demucs vocal isolation. "
        "All inference runs on this machine."
    ),
    lifespan=lifespan,
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )


# ── Error handler ───────────────────────────────────────────────
@app.exception_handler(Exception)
async def _unhandled(_req, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(error=str(type(exc).__name__), detail=str(exc)).model_dump(),
    )


# ── Web UI ───────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/ui", StaticFiles(directory=str(STATIC_DIR), html=True), name="ui")


# ── Health / metadata ────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/ui/")


@app.get("/api", response_model=dict)
async def api_root():
    return {
        "service": "qwen3-tts-api",
        "version": "1.0.0",
        "ui": "/ui/",
        "docs": "/docs",
        "llms_txt": "/llms.txt",
        "openapi": "/openapi.json",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse)
async def health(_: str = Depends(require_auth)):
    s = engine.status()
    return HealthResponse(
        status="ok" if s["loaded_model"] else "loading",
        loaded_model=s["loaded_model"],
        available_models=s["available_models"],
        device=s["device"], dtype=s["dtype"], attention=s["attention"],
    )


@app.get("/v1/models", response_model=ModelsResponse)
async def list_models(_: str = Depends(require_auth)):
    return ModelsResponse(
        models=[k.value for k in ModelKey],
        capabilities={cap: [k.value for k in keys] for cap, keys in SUPPORTED.items()},
    )


@app.get("/v1/languages", response_model=LanguagesResponse)
async def list_languages(model: str | None = None, _: str = Depends(require_auth)):
    langs = await asyncio.to_thread(engine.supported_languages, model)
    return LanguagesResponse(languages=langs, model=model or settings.default_model)


@app.get("/v1/speakers", response_model=SpeakersResponse)
async def list_speakers(model: str | None = None, _: str = Depends(require_auth)):
    speakers = await asyncio.to_thread(engine.supported_speakers, model)
    return SpeakersResponse(speakers=speakers, model=model or "customvoice-0.6b")


# ── Voices ───────────────────────────────────────────────────────
def _voice_to_info(m) -> VoiceInfo:
    return VoiceInfo(
        voice_id=m.voice_id,
        name=m.name,
        language=m.language,
        has_transcript=bool(m.transcript),
        filename=m.filename,
        size_bytes=m.size_bytes,
        duration_s=m.duration_s,
        created_at=m.created_at,
        tags=m.tags,
    )


@app.get("/v1/voices", response_model=VoicesResponse)
async def list_voices(_: str = Depends(require_auth)):
    voices = [_voice_to_info(m) for m in store.list_all()]
    return VoicesResponse(voices=voices)


@app.get("/v1/voices/{voice_id}", response_model=VoiceInfo)
async def get_voice(voice_id: str, _: str = Depends(require_auth)):
    m = store.get(voice_id)
    if m is None:
        raise HTTPException(404, f"Voice '{voice_id}' not found")
    return _voice_to_info(m)


@app.post("/v1/voices", response_model=VoiceInfo, status_code=201)
async def upload_voice(
    file: UploadFile = File(..., description="Audio file (wav, mp3, flac, ogg, m4a)"),
    name: str | None = Form(None),
    language: str = Form("English"),
    transcript: str | None = Form(None),
    tags: str = Form(""),  # comma-separated
    _: str = Depends(require_auth),
):
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty upload")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    try:
        meta = await asyncio.to_thread(
            store.create, content, file.filename or "voice.wav",
            name, language, transcript, tag_list,
        )
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _voice_to_info(meta)


@app.patch("/v1/voices/{voice_id}", response_model=VoiceInfo)
async def update_voice(voice_id: str, body: VoiceUpdateRequest, _: str = Depends(require_auth)):
    try:
        meta = await asyncio.to_thread(
            store.update, voice_id, body.name, body.language, body.transcript, body.tags,
        )
    except KeyError as e:
        raise HTTPException(404, str(e))
    return _voice_to_info(meta)


@app.delete("/v1/voices/{voice_id}", status_code=204)
async def delete_voice(voice_id: str, _: str = Depends(require_auth)):
    ok = await asyncio.to_thread(store.delete, voice_id)
    if not ok:
        raise HTTPException(404, f"Voice '{voice_id}' not found")
    return None


@app.get("/v1/voices/{voice_id}/audio")
async def download_voice(voice_id: str, _: str = Depends(require_auth)):
    try:
        meta = store.require(voice_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    return FileResponse(str(meta.path), filename=meta.filename, media_type="audio/wav")


# ── Output saving helper ─────────────────────────────────────────
def _save_output(result, request) -> AudioResponse:
    """Write result to outputs dir, return AudioResponse with url or base64."""
    settings.outputs_dir.mkdir(exist_ok=True)
    output_id = uuid.uuid4().hex[:16]
    out_path = settings.outputs_dir / f"{output_id}.wav"
    save_wav(result, out_path)
    resp = AudioResponse(
        sample_rate=result.sample_rate,
        duration_s=result.duration_s,
        model=result.model,
        text_chars=result.text_chars,
    )
    if request.output_format == "wav_base64":
        with open(out_path, "rb") as f:
            resp.audio_base64 = base64.b64encode(f.read()).decode("ascii")
        try:
            os.remove(out_path)
        except OSError:
            pass
    else:
        rel = f"/v1/outputs/{output_id}.wav"
        resp.url = rel
    return resp


# ── TTS endpoints ────────────────────────────────────────────────
@app.post("/v1/tts/voice-clone", response_model=AudioResponse)
async def tts_voice_clone(req: VoiceCloneRequest, _: str = Depends(require_auth)):
    if len(req.text) > settings.max_text_chars:
        raise HTTPException(400, f"Text too long: {len(req.text)} chars (max {settings.max_text_chars})")
    # Resolve voice IDs to paths.
    ref_paths: list[str] = []
    for vid in req.voice_ids:
        try:
            ref_paths.append(str(store.path_for(vid)))
        except KeyError:
            raise HTTPException(404, f"Voice '{vid}' not found")
    transcripts = req.transcripts
    if transcripts and len(transcripts) != len(req.voice_ids):
        raise HTTPException(400, "transcripts length must match voice_ids")
    try:
        result = await asyncio.to_thread(
            engine.voice_clone,
            text=req.text, ref_audio=ref_paths,
            language=req.language,
            ref_text=transcripts,
            x_vector_only=req.x_vector_only,
            model=req.model,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        log.exception("voice_clone failed")
        raise HTTPException(500, f"TTS generation failed: {e}")
    return _save_output(result, req)


@app.post("/v1/tts/voice-design", response_model=AudioResponse)
async def tts_voice_design(req: VoiceDesignRequest, _: str = Depends(require_auth)):
    if len(req.text) > settings.max_text_chars:
        raise HTTPException(400, f"Text too long: {len(req.text)} chars")
    try:
        result = await asyncio.to_thread(
            engine.voice_design,
            text=req.text, instruct=req.instruct,
            language=req.language, model=req.model,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        log.exception("voice_design failed")
        raise HTTPException(500, f"TTS generation failed: {e}")
    return _save_output(result, req)


@app.post("/v1/tts/custom-voice", response_model=AudioResponse)
async def tts_custom_voice(req: CustomVoiceRequest, _: str = Depends(require_auth)):
    if len(req.text) > settings.max_text_chars:
        raise HTTPException(400, f"Text too long: {len(req.text)} chars")
    try:
        result = await asyncio.to_thread(
            engine.custom_voice,
            text=req.text, speaker=req.speaker,
            language=req.language, instruct=req.instruct, model=req.model,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        log.exception("custom_voice failed")
        raise HTTPException(500, f"TTS generation failed: {e}")
    return _save_output(result, req)


# ── Output download ─────────────────────────────────────────────
@app.get("/v1/outputs/{output_id}.wav")
async def get_output(output_id: str, _: str = Depends(require_auth)):
    # Reject anything that isn't a hex slug.
    if not all(c in "0123456789abcdef" for c in output_id):
        raise HTTPException(404, "Not found")
    path = settings.outputs_dir / f"{output_id}.wav"
    if not path.exists():
        raise HTTPException(404, "Output expired or not found")
    if path.stat().st_mtime < time.time() - settings.output_ttl_seconds:
        with suppress(OSError):
            path.unlink()
        raise HTTPException(404, "Output expired or not found")
    return FileResponse(str(path), filename=f"{output_id}.wav", media_type="audio/wav")


# ── Transcription (faster-whisper) ──────────────────────────────
_whisper_model = None
_whisper_lock = asyncio.Lock()


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model


def _transcribe_file(path: str) -> str:
    model = _get_whisper()
    segments, _info = model.transcribe(path, vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip()


@app.post("/v1/voices/{voice_id}/transcribe")
async def transcribe_voice(voice_id: str, _: str = Depends(require_auth)):
    """Auto-transcribe a stored voice with faster-whisper and save as its transcript."""
    try:
        meta = store.require(voice_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    async with _whisper_lock:  # whisper model is not thread-safe; serialize
        try:
            transcript = await asyncio.to_thread(_transcribe_file, str(meta.path))
        except Exception as e:
            log.exception("transcription failed")
            raise HTTPException(500, f"Transcription failed: {e}")
    if not transcript:
        raise HTTPException(422, "No speech detected in this audio")
    updated = await asyncio.to_thread(store.update, voice_id, None, None, transcript, None)
    return {"voice_id": voice_id, "transcript": updated.transcript}


# ── Vocal isolation ─────────────────────────────────────────────
@app.post("/v1/audio/isolate-vocals", response_model=IsolateVocalsResponse)
async def isolate_vocals(req: IsolateVocalsRequest, _: str = Depends(require_auth)):
    """Run demucs on a stored voice and create a new voice with the isolated vocals."""
    try:
        meta = store.require(req.voice_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    out_dir = Path(tempfile.mkdtemp(prefix="demucs_"))
    try:
        proc = await asyncio.create_subprocess_exec(
            "demucs",
            "--device", "cpu",
            str(meta.path),
            "-o", str(out_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise HTTPException(500, f"demucs failed: {stderr.decode(errors='ignore')[:500]}")
        vocals_path = out_dir / "htdemucs" / meta.path.stem / "vocals.wav"
        if not vocals_path.exists():
            raise HTTPException(500, "demucs produced no vocals.wav")
        # Create a new voice from the isolated vocals.
        with open(vocals_path, "rb") as f:
            content = f.read()
        import soundfile as sf
        info = sf.info(str(vocals_path))
        new_meta = await asyncio.to_thread(
            store.create, content, "vocals.wav",
            name=f"{meta.name}-vocals", language=meta.language,
            transcript=meta.transcript, tags=(meta.tags or []) + ["vocals-only"],
        )
        return IsolateVocalsResponse(
            voice_id=req.voice_id,
            vocals_voice_id=new_meta.voice_id,
            duration_s=info.duration,
            size_bytes=new_meta.size_bytes,
        )
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


# ── LLMs.txt — AI discovery ─────────────────────────────────────
@app.get("/llms.txt", response_class=JSONResponse)
async def llms_txt():
    """AI-discovery manifest. Lists endpoints and how to use them."""
    return {
        "name": "qwen3-tts-api",
        "description": "Local Qwen3-TTS text-to-speech inference service.",
        "version": "1.0.0",
        "web_ui": "/ui/",
        "auth": "Bearer token in Authorization header. TTS_API_KEYS env var (comma-separated).",
        "endpoints": {
            "GET /health": "Service health + loaded model + device info.",
            "GET /v1/models": "List available models and their capabilities.",
            "GET /v1/languages?model=...": "Supported languages for a model.",
            "GET /v1/speakers?model=...": "Built-in speakers for CustomVoice models.",
            "GET /v1/voices": "List uploaded reference voices.",
            "POST /v1/voices": "Upload a reference voice (multipart: file, name, language, transcript, tags).",
            "GET /v1/voices/{id}": "Get voice metadata.",
            "PATCH /v1/voices/{id}": "Update voice name/transcript/tags.",
            "DELETE /v1/voices/{id}": "Delete a voice.",
            "GET /v1/voices/{id}/audio": "Download the original audio file.",
            "POST /v1/tts/voice-clone": "Clone voice from 1-5 voices + synthesize. Body: {text, voice_ids:[...], transcripts?:[...], x_vector_only?, language?, model?, output_format?}.",
            "POST /v1/tts/voice-design": "Design a voice from a text description. Body: {text, instruct, language?, model?, output_format?}.",
            "POST /v1/tts/custom-voice": "Use a built-in speaker. Body: {text, speaker, language?, instruct?, model?, output_format?}.",
            "POST /v1/voices/{id}/transcribe": "Auto-transcribe a stored voice (faster-whisper) and save as its transcript. Returns {voice_id, transcript}.",
            "POST /v1/audio/isolate-vocals": "Strip background music from a stored voice (demucs). Body: {voice_id}. Returns a new voice_id with isolated vocals.",
            "GET /v1/outputs/{id}.wav": "Download a previously generated output (when output_format='url').",
        },
        "models": {
            "base-0.6b": "Voice clone from reference audio. 0.9B params. Faster.",
            "base-1.7b": "Voice clone from reference audio. 2B params. Higher quality.",
            "customvoice-0.6b": "Built-in speaker presets.",
            "customvoice-1.7b": "Built-in speaker presets, larger model.",
            "voicedesign-1.7b": "Generate voice from text description (e.g. 'deep Scottish male, gravelly').",
        },
        "output_format": "wav_base64 returns audio in JSON as base64 string. url returns a download URL (output expires after TTS_OUTPUT_TTL seconds).",
        "languages": ["auto", "chinese", "english", "french", "german", "italian", "japanese", "korean", "portuguese", "russian", "spanish"],
        "rate_limits": "None enforced. Inference is bounded by GPU/CPU throughput — one model swap per request is the slowest path.",
        "error_format": "JSON {error: string, detail: string?} with appropriate HTTP status.",
    }
