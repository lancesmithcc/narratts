# Deployment

NarraTTS is designed as a single-machine inference service. One process is recommended because the
engine keeps one model in memory and serializes model swaps.

## Docker

```bash
cp .env.example .env
# Set TTS_API_KEYS to a strong random value and TTS_HOST=0.0.0.0
docker compose up --build
```

Open <http://127.0.0.1:8765>. Docker uses named volumes for NarraTTS data and Hugging Face model
caches. The included image is CPU-oriented; GPU passthrough requires an NVIDIA Container Toolkit
host and a CUDA-compatible PyTorch image/build.

## Reverse proxy

Terminate HTTPS at Caddy, nginx, Traefik, or another trusted proxy. Forward to
`127.0.0.1:8765`, preserve the `Authorization` header, set a request-body limit matching
`TTS_MAX_VOICE_BYTES`, and use long upstream timeouts because synthesis and model swaps can take
minutes.

Example Caddy configuration:

```caddyfile
tts.example.com {
    reverse_proxy 127.0.0.1:8765
    request_body {
        max_size 50MB
    }
}
```

## Service manager

Run the process from its virtual environment under systemd, launchd, or another process manager:

```bash
/path/to/narratts/.venv/bin/narratts --host 127.0.0.1 --port 8765
```

Use one worker. Multiple Uvicorn workers each load separate model weights and do not share the
voice-model cache.

## Production checklist

- Strong `TTS_API_KEYS` configured and rotated.
- HTTPS reverse proxy enabled for remote access.
- `TTS_ALLOW_UNAUTHENTICATED=false`.
- Firewall limits access to the proxy.
- Persistent `TTS_DATA_DIR` backed up and permission-restricted.
- Sufficient disk for model caches and sufficient RAM/VRAM for chosen model.
- Consent obtained for every cloned voice; generated audio labeled where appropriate.
