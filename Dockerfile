FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TTS_HOST=0.0.0.0 \
    TTS_DATA_DIR=/data \
    HF_HOME=/models/huggingface

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 sox \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN python -m pip install --upgrade pip \
    && python -m pip install ".[audio-tools]"

RUN useradd --create-home --uid 10001 narratts \
    && mkdir -p /data /models/huggingface \
    && chown -R narratts:narratts /data /models /app
USER narratts

EXPOSE 8765
CMD ["narratts"]
