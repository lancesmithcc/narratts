# NarraTTS

Self-hosted Qwen3-TTS studio and FastAPI service for voice cloning, voice design, built-in
speakers, transcription, and vocal isolation.

NarraTTS runs inference on your own machine. Reference audio, prompts, and generated speech are
not sent to a hosted inference API. The web interface currently loads Three.js from jsDelivr and
Space Grotesk from Google Fonts; see [NOTICE](NOTICE).

> Use voice cloning responsibly. Obtain permission from the speaker, follow applicable law, and
> disclose synthetic speech where people could reasonably mistake it for a real recording.

## Features

- Local Qwen3-TTS inference on Apple Silicon, NVIDIA CUDA, or CPU
- Voice clone from one to five uploaded reference clips
- Voice creation from a natural-language description
- Qwen built-in speaker presets and style instructions
- Browser voice library with upload, recording, playback, editing, and deletion
- Optional faster-whisper transcription and Demucs vocal isolation
- JSON API with Bearer authentication, OpenAPI, Swagger UI, and ReDoc
- Installable `narratts` command and Docker setup
- No frontend build step

## Quick start

Python 3.12 is recommended. Install FFmpeg, libsndfile, and SoX first.

```bash
git clone https://github.com/lancesmithcc/narratts.git
cd narratts
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[audio-tools]"
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Put the generated token in `.env` as `TTS_API_KEYS`, then start the service:

```bash
narratts
```

Open <http://127.0.0.1:8765>. Click **key** and enter the same token.

The first use of a model downloads its weights from Hugging Face and can take several minutes.
Later requests reuse the local cache.

## Docker

```bash
cp .env.example .env
# Set a strong TTS_API_KEYS value in .env
docker compose up --build
```

Open <http://127.0.0.1:8765>. The included image is CPU-oriented; see
[deployment documentation](docs/DEPLOYMENT.md) for GPU and reverse-proxy notes.

## Basic API use

```bash
export TTS_KEY="your-key"

# Upload a reference voice
curl -X POST http://127.0.0.1:8765/v1/voices \
  -H "Authorization: Bearer $TTS_KEY" \
  -F "file=@sample.wav" \
  -F "name=My narrator" \
  -F "language=English"

# Clone it; replace the id with the upload response
curl -X POST http://127.0.0.1:8765/v1/tts/voice-clone \
  -H "Authorization: Bearer $TTS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello from NarraTTS.",
    "voice_ids": ["my-narrator-abc1234567"],
    "x_vector_only": true,
    "output_format": "url"
  }'
```

Interactive documentation is available while the server runs:

- Web studio: <http://127.0.0.1:8765/ui/>
- Swagger UI: <http://127.0.0.1:8765/docs>
- ReDoc: <http://127.0.0.1:8765/redoc>
- OpenAPI JSON: <http://127.0.0.1:8765/openapi.json>
- AI discovery manifest: <http://127.0.0.1:8765/llms.txt>

## Models

| NarraTTS key | Qwen model | Capability |
|---|---|---|
| `base-0.6b` | `Qwen3-TTS-12Hz-0.6B-Base` | Faster voice cloning |
| `base-1.7b` | `Qwen3-TTS-12Hz-1.7B-Base` | Higher-quality voice cloning; default |
| `voicedesign-1.7b` | `Qwen3-TTS-12Hz-1.7B-VoiceDesign` | Voice from description |
| `customvoice-0.6b` | `Qwen3-TTS-12Hz-0.6B-CustomVoice` | Built-in speakers |
| `customvoice-1.7b` | `Qwen3-TTS-12Hz-1.7B-CustomVoice` | Larger built-in-speaker model |

NarraTTS supports the ten languages published for these Qwen models: Chinese, English, Japanese,
Korean, German, French, Russian, Portuguese, Spanish, and Italian.

## Hardware

- **Apple Silicon:** MPS with float32 and SDPA. Tested locally on an M-series Mac.
- **NVIDIA:** CUDA with bfloat16; FlashAttention 2 is used when installed.
- **CPU:** Supported, but slow. Prefer a 0.6B model and shorter inputs.

Actual memory use and generation speed depend on model, text length, dependency versions, and
hardware. Model weights require several gigabytes of storage.

## Configuration

Copy `.env.example` to `.env`. Important defaults:

| Variable | Default | Purpose |
|---|---:|---|
| `TTS_HOST` | `127.0.0.1` | Safe loopback bind |
| `TTS_PORT` | `8765` | HTTP port |
| `TTS_API_KEYS` | empty | Comma-separated Bearer tokens |
| `TTS_DATA_DIR` | `~/.narratts` | Persistent voice/output storage |
| `TTS_DEFAULT_MODEL` | `base-1.7b` | Startup/default clone model |
| `TTS_WARM_ON_START` | `true` | Preload default model |
| `TTS_OUTPUT_TTL` | `3600` | URL-output lifetime in seconds |

NarraTTS refuses an unauthenticated non-loopback bind unless you explicitly set
`TTS_ALLOW_UNAUTHENTICATED=true`. See [configuration documentation](docs/CONFIGURATION.md) for all
settings and deployment cautions.

## Data and privacy

Runtime data defaults to `~/.narratts`:

```text
~/.narratts/
├── voices/   # uploaded references and metadata
├── outputs/  # temporary URL-based generated WAVs
└── samples/  # optional local samples
```

These directories, `.env`, certificates, logs, personal audio, and generated outputs are excluded
from Git. Voice recordings may be sensitive personal or biometric data; use restrictive filesystem
permissions and backups appropriate to your environment.

## Documentation

- [Installation and troubleshooting](docs/INSTALLATION.md)
- [Configuration reference](docs/CONFIGURATION.md)
- [Deployment guide](docs/DEPLOYMENT.md)
- [AI-agent/API guide](service/docs/AI_GUIDE.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Product behavior](PRODUCT.md) and [interface design](DESIGN.md)

## Development

```bash
python -m pip install -e ".[audio-tools,dev]"
pytest
ruff check .
python -m build
narratts --no-warm --reload
```

The frontend is plain HTML, CSS, and JavaScript under `service/static/`. `--no-warm` is useful for
UI/API work because it avoids loading model weights at startup.

## Legacy CLI

The original script remains available for direct workflows:

```bash
python qwen3_tts.py voice-clone \
  --text "Hello" \
  --ref-audio sample.wav \
  --x-vector-only \
  --output output.wav
```

Run `python qwen3_tts.py --help` for commands and options.

## License and upstream

NarraTTS is licensed under [Apache-2.0](LICENSE). It is an independent interface built on
[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS). Qwen software and model weights retain their own
license notices and terms. NarraTTS is not affiliated with or endorsed by the Qwen team.
