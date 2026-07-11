# Installation

NarraTTS is tested primarily with Python 3.12. Model weights download on first use and need
several gigabytes of free disk space.

## macOS (Apple Silicon)

Install Python 3.12, FFmpeg, libsndfile, and SoX using Homebrew:

```bash
brew install python@3.12 ffmpeg libsndfile sox
git clone https://github.com/lancesmithcc/narratts.git
cd narratts
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[audio-tools]"
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Put the generated token in `TTS_API_KEYS` inside `.env`, then run:

```bash
narratts
```

Open <http://127.0.0.1:8765> and enter the same key using the **key** button.

## Linux with NVIDIA CUDA

Install Python 3.12, FFmpeg, libsndfile, and SoX with your package manager. Install a CUDA-compatible
PyTorch build using the [official PyTorch selector](https://pytorch.org/get-started/locally/) before
installing NarraTTS. Then follow the virtual-environment steps above.

FlashAttention 2 is optional but recommended on compatible NVIDIA GPUs:

```bash
MAX_JOBS=4 python -m pip install flash-attn --no-build-isolation
```

Do not install FlashAttention on Apple Silicon or CPU-only systems.

## CPU-only

The same install works on CPU, but synthesis can be slow and the 1.7B models require substantial
memory. Start with `TTS_DEFAULT_MODEL=base-0.6b`.

## Minimal install

The default project dependencies provide TTS. Transcription and vocal isolation are optional:

```bash
python -m pip install -e .                 # TTS only
python -m pip install -e ".[audio-tools]" # + Whisper and Demucs
```

## Upgrading

```bash
git pull --ff-only
source .venv/bin/activate
python -m pip install --upgrade -e ".[audio-tools]"
```

Runtime voices and generated files live under `~/.narratts` by default and are not touched by an
upgrade.

## Troubleshooting installation

- `SoX could not be found`: install `sox` with Homebrew or your OS package manager.
- `soundfile` cannot load libsndfile: install `libsndfile`.
- CUDA out of memory: use a 0.6B model, shorten text, or run on CPU.
- Hugging Face download fails: verify network access; set `HF_TOKEN` only if the selected model
  requires authentication.
- First generation appears stuck: watch terminal logs. Initial model download/load can take minutes.
