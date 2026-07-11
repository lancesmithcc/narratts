# Configuration

NarraTTS reads environment variables and a project-root `.env` file. Environment variables already
present in the shell take precedence. Copy `.env.example` to `.env`; never commit `.env`.

| Variable | Default | Description |
|---|---:|---|
| `TTS_HOST` | `127.0.0.1` | Bind address. Use `0.0.0.0` only for containers or trusted LAN access. |
| `TTS_PORT` | `8765` | HTTP port. |
| `TTS_API_KEYS` | empty | Comma-separated Bearer tokens. Strongly recommended. |
| `TTS_ALLOW_UNAUTHENTICATED` | `false` | Permit a non-loopback bind without keys. Unsafe on shared networks. |
| `TTS_CORS_ORIGINS` | empty | Comma-separated browser origins. Empty means same-origin only. |
| `TTS_DEFAULT_MODEL` | `base-1.7b` | Model warmed at startup and default for voice cloning. |
| `TTS_WARM_ON_START` | `true` | Preload the default model in the background. |
| `TTS_DATA_DIR` | `~/.narratts` | Persistent voices and temporary generated outputs. |
| `TTS_LOG_LEVEL` | `info` | Uvicorn/application log level. |
| `TTS_MAX_TEXT_CHARS` | `2000` | Maximum request text length. |
| `TTS_MAX_REFS` | `5` | Maximum clone references per request. |
| `TTS_MAX_VOICE_BYTES` | `50000000` | Maximum uploaded reference size. |
| `TTS_OUTPUT_TTL` | `3600` | Lifetime in seconds for URL-based generated WAV files. |
| `HF_TOKEN` | empty | Optional Hugging Face access token. |

## API keys

Generate a key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Multiple keys allow separate clients and easy rotation:

```dotenv
TTS_API_KEYS=key-for-browser,key-for-automation
```

## Network safety

With no API key, NarraTTS accepts requests only when bound to a loopback address. A non-loopback
bind fails at startup unless `TTS_ALLOW_UNAUTHENTICATED=true` is explicitly set.

NarraTTS serves plain HTTP. For internet-facing deployment, put it behind a TLS reverse proxy,
keep Bearer authentication enabled, restrict upload size at the proxy, and do not expose it as an
unmetered public service.

## Data layout

```text
~/.narratts/
├── voices/          Uploaded reference audio and metadata
├── outputs/         URL-based generated WAVs, removed after their TTL
└── samples/         Optional local samples
```

Back up `voices/` if the library matters. Voice uploads may contain biometric and personal data;
protect the directory accordingly.
