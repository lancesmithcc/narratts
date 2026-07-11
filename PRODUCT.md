# PRODUCT.md — Qwen3 TTS Studio

## Product purpose
Web control surface for the local Qwen3-TTS FastAPI service (`service/app.py`, port 8765). Generate speech (built-in speakers, voice design from text description), clone voices from reference audio, manage the voice library, isolate vocals, and read the API docs. Everything runs on the user's own Mac; no cloud.

## Users
Creators, developers, accessibility teams, and audio tinkerers who want local speech generation without sending voice samples to a hosted inference API. The interface prioritizes speed, keyboard-friendly flow, and the feel of a crafted studio instrument rather than an admin panel.

## Register
product — a working tool. But it is a personal studio instrument, so it carries more identity than a typical dashboard: one committed accent, expressive motion tied to sound.

## Tone
Precise, warm, quietly confident. Copy is short and concrete. No SaaS hype, no exclamation marks.

## Anti-references
- Generic AI-tool slop: neon cyan/purple on pure black, glassmorphism cards, gradient text.
- Swagger-style utilitarian docs walls.
- ElevenLabs clone look.

## Strategic principles
1. Text box first: the fastest path is type → pick voice → generate → hear it.
2. Sound is visible: the swarm/waveform animation is the product's signature, reactive to pointer, click, scroll, and live audio playback.
3. Local and honest: show device, loaded model, and real latency; never fake progress.
4. Docs live in the house: API reference is a first-class tab, same aesthetic, copy-paste ready curl.
