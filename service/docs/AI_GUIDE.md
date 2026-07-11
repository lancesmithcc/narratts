# Qwen3-TTS API — AI Agent Guide

This guide is written for an AI agent (LLM with tool-use) that needs to drive the Qwen3-TTS service. It covers the **minimum knowledge needed to use the API successfully**, including common pitfalls.

## TL;DR

- **Base URL**: `http://localhost:8765` (default; override with `TTS_HOST` / `TTS_PORT`)
- **Auth**: configure `TTS_API_KEYS`, then send `Authorization: Bearer <key>`. Auth may be disabled only for a loopback development bind.
- **All endpoints are JSON** (except uploads and audio downloads).
- **Generated audio**: either `audio_base64` (string in JSON) or a download URL you fetch within the TTL.
- **First request can be slow** (~10-30s) because the model loads. Subsequent same-model requests are fast (1-5s for typical text).

## Auth

Every request after `/` requires this header:

```
Authorization: Bearer <TTS_API_KEYS value>
```

Keys are configured server-side via the `TTS_API_KEYS` env var (comma-separated). If the server has `TTS_API_KEYS=""` (empty), auth is disabled — only do this in development.

If you get a `401`: header missing. `403`: key wrong.

## Models

The service supports 5 models. Each has different capabilities:

| Model | Voice clone | Voice design | Custom voice |
|---|---|---|---|
| `base-0.6b` | ✅ | ❌ | ❌ |
| `base-1.7b` | ✅ (default) | ❌ | ❌ |
| `voicedesign-1.7b` | ❌ | ✅ | ❌ |
| `customvoice-0.6b` | ❌ | ❌ | ✅ |
| `customvoice-1.7b` | ❌ | ❌ | ✅ |

If you call the wrong endpoint with the wrong model you get a `400`.

**Don't hardcode model keys unless necessary.** If you omit `model`, the server uses `base-1.7b` for voice-clone. That is fine for most cases.

## Common workflow: voice clone

The most common use case. Steps:

1. **Upload a reference voice** (or several). The audio should be a clean sample of the voice — 5-30 seconds is ideal.

   ```bash
   curl -X POST http://localhost:8765/v1/voices \
     -H "Authorization: Bearer $TTS_KEY" \
     -F "file=@/path/to/sample.wav" \
     -F "name=my-voice" \
     -F "language=English" \
     -F "transcript=What the speaker actually said in sample.wav"
   ```

   Returns:
   ```json
   {
     "voice_id": "my-voice-7f3a9c0b1d",
     "name": "my-voice",
     "language": "English",
     "has_transcript": true,
     "filename": "voice.wav",
     "size_bytes": 245760,
     "duration_s": 8.2,
     "created_at": 1717800000.0,
     "tags": []
   }
   ```

   **Important:** the `voice_id` is auto-generated from the file's content hash + your name. Two uploads of the same file produce the same `voice_id` and you'll get a `409 Conflict`. If you want to "update" a voice, delete it first.

   **If you don't know the transcript**, omit the `transcript` field and pass `"x_vector_only": true` in the synthesis call. Quality is slightly worse without a transcript but still usable.

2. **Synthesize speech**:

   ```bash
   curl -X POST http://localhost:8765/v1/tts/voice-clone \
     -H "Authorization: Bearer $TTS_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "text": "Hello, this is my cloned voice speaking.",
       "voice_ids": ["my-voice-7f3a9c0b1d"],
       "x_vector_only": true,
       "language": "english"
     }'
   ```

   Returns either:
   ```json
   {
     "audio_base64": "//uQxAAD...",
     "sample_rate": 24000,
     "duration_s": 3.2,
     "format": "wav",
     "model": "base-1.7b",
     "text_chars": 39
   }
   ```

   …or, if you pass `"output_format": "url"`:
   ```json
   {
     "url": "/v1/outputs/abc123def4567890.wav",
     "sample_rate": 24000,
     ...
   }
   ```

   Then `GET http://localhost:8765/v1/outputs/abc123def4567890.wav` (with auth header) returns the WAV file.

3. **Save or play the audio**: decode `audio_base64` to bytes, save as `.wav`. Standard 24kHz 16-bit PCM.

### Improving voice clone quality

- **More reference audio is better.** Upload up to 5 clips of the same speaker; the service averages their voice embeddings for a richer profile.
- **Longer clips** (10-30s each) outperform short ones.
- **Transcripts dramatically improve quality** when you have them.
- **Clean audio wins.** If your reference has background music, call `/v1/audio/isolate-vocals` first to create a cleaned-up voice, then use that voice_id for synthesis.

## Voice design (no reference needed)

Synthesize speech in a voice described entirely by text:

```bash
curl -X POST http://localhost:8765/v1/tts/voice-design \
  -H "Authorization: Bearer $TTS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "I am solving the equation x equals negative b plus or minus square root of b squared minus 4ac, all divided by 2a.",
    "instruct": "A middle-aged Scottish man from Glasgow, nasal and raspy voice, thick rolling R sounds, broad Scottish accent, working class."
  }'
```

The `instruct` field is a freeform voice description. **Be specific**: mention age, gender, accent, vocal qualities (raspy, breathy, deep), emotional register. The model interprets English descriptions.

To make voices sound more Scottish, also write the text in Scots dialect (e.g. "Ach, gather roond" instead of "Ah, gather round"). The model uses both the instruct and the text spelling to determine pronunciation.

## Custom voice (built-in speakers)

Some models ship with preset speakers. List them first:

```bash
curl http://localhost:8765/v1/speakers -H "Authorization: Bearer $TTS_KEY"
```

Then use one:

```bash
curl -X POST http://localhost:8765/v1/tts/custom-voice \
  -H "Authorization: Bearer $TTS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "speaker": "ryan"
  }'
```

## Voice library management

| Action | Method |
|---|---|
| List voices | `GET /v1/voices` |
| Get one | `GET /v1/voices/{id}` |
| Upload | `POST /v1/voices` (multipart) |
| Edit metadata | `PATCH /v1/voices/{id}` (JSON) |
| Download audio | `GET /v1/voices/{id}/audio` |
| Delete | `DELETE /v1/voices/{id}` |

## Vocal isolation

If you have audio with music/noise and you want to use it as a voice reference:

```bash
curl -X POST http://localhost:8765/v1/audio/isolate-vocals \
  -H "Authorization: Bearer $TTS_KEY" \
  -H "Content-Type: application/json" \
  -d '{"voice_id": "noisy-sample-abc123"}'
```

Returns `{voice_id, vocals_voice_id, duration_s, size_bytes}`. The new `vocals_voice_id` is the cleaned-up version, ready for voice cloning. This runs **demucs** and takes 30-60s for a typical song.

## Tips for AI agents

1. **Always check `GET /v1/voices` first** to see what reference voices already exist — don't re-upload.

2. **Use `x_vector_only: true`** unless you have a perfect transcript. It saves you from having to transcribe.

3. **For multiple references**, list them in `voice_ids` as an array. The service averages their embeddings — voice quality improves with more samples.

4. **Language codes** are lowercase: `"english"`, `"chinese"`, `"japanese"`, etc. The Base model also accepts `"auto"` for auto-detection.

5. **Text length limits**: 2000 chars per request. For longer text, split into chunks and synthesize separately, then concatenate the WAVs offline (e.g. with `soundfile` + `numpy.concatenate`).

6. **The first request is slow.** The server warms the default model in the background, but if you specify a different model your first request to it triggers a load (~15s). Subsequent requests with that model are fast.

7. **Output TTL**: when you use `output_format: "url"`, the URL is valid for `TTS_OUTPUT_TTL` seconds (default 3600 = 1 hour). After that, `GET` returns 404.

8. **Errors are JSON**: `{"error": "ValueError", "detail": "..."}`. HTTP status is meaningful (400 = bad input, 404 = not found, 500 = generation failed).

9. **Don't pollute the voices directory**: each upload creates a folder on disk. Delete voices you no longer need.

10. **For Scottish / Scottish-accent voices**: combine these signals:
    - Reference voice with thick Scottish accent (use vocal isolation first if needed)
    - `x_vector_only: true` to avoid transcript mismatch
    - Optionally: text written in Scots dialect spelling ("och", "nae", "ye", "wis", "dinnae")
    - Model: `base-1.7b` (default; better than 0.6b for nuanced voices)

## Discovery

- `/llms.txt` returns a JSON manifest of endpoints (good for AI systems that want a structured index).
- `/docs` returns Swagger UI (interactive).
- `/openapi.json` returns the full OpenAPI 3 spec — load this for schema-aware clients.
- `/redoc` returns a polished read-only API reference.

## Quick reference: Python client

```python
import base64, requests

API = "http://localhost:8765"
KEY = "replace-with-your-configured-key"
H = {"Authorization": f"Bearer {KEY}"}

# 1. Upload a voice
with open("sample.wav", "rb") as f:
    r = requests.post(f"{API}/v1/voices", headers=H,
                      files={"file": ("sample.wav", f, "audio/wav")},
                      data={"name": "narrator", "language": "English"})
voice_id = r.json()["voice_id"]

# 2. Synthesize
r = requests.post(f"{API}/v1/tts/voice-clone", headers=H, json={
    "text": "Hey ye wee bastards.",
    "voice_ids": [voice_id],
    "x_vector_only": True,
})
audio_b64 = r.json()["audio_base64"]
with open("out.wav", "wb") as f:
    f.write(base64.b64decode(audio_b64))
```

## Quick reference: cURL

```bash
# Upload
curl -X POST http://localhost:8765/v1/voices \
  -H "Authorization: Bearer $TTS_KEY" \
  -F file=@sample.wav -F name=narrator

# Synthesize
curl -X POST http://localhost:8765/v1/tts/voice-clone \
  -H "Authorization: Bearer $TTS_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello","voice_ids":["narrator-abc123"],"x_vector_only":true}'
```

## Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| 401 Unauthorized | Missing/wrong Bearer token | Add `Authorization: Bearer <key>` |
| 404 on voice_id | Voice not uploaded (or wrong ID) | `GET /v1/voices` to list |
| 409 on upload | Same audio uploaded before | Delete existing voice, then re-upload |
| 400 "Model X does not support Y" | Wrong model for endpoint | See model table above |
| 400 "Text too long" | >2000 chars | Split into chunks |
| Slow first request | Model loading | Wait; subsequent requests fast |
| Empty audio | Engine error | Check server logs; usually bad ref audio |
