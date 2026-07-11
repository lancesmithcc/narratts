# Qwen3-TTS API Service Makefile
# Run `make help` for commands.

PY ?= python3
PORT ?= 8765
HOST ?= 0.0.0.0

.PHONY: help install install-core run dev test lint build clean

help:  ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "%-15s %s\n", $$1, $$2}'

install:  ## Install Python dependencies.
	$(PY) -m pip install -U -e ".[audio-tools]"

install-core:  ## Install TTS without optional transcription/isolation tools.
	$(PY) -m pip install -U -e .

run:  ## Start the service (foreground).
	$(PY) -m service.cli --host $(HOST) --port $(PORT)

dev:  ## Run with hot reload.
	$(PY) -m service.cli --host $(HOST) --port $(PORT) --reload

test:  ## Run unit tests.
	$(PY) -m pytest

lint:  ## Run static checks.
	$(PY) -m ruff check .

build:  ## Build wheel and source archive.
	$(PY) -m build

clean:  ## Clear cached generated outputs (TTL still applies).
	rm -rf dist build .pytest_cache .ruff_cache
