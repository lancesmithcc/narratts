# Contributing

Issues and pull requests are welcome.

## Development setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[audio-tools,dev]"
cp .env.example .env
pytest
ruff check .
```

Use `narratts --no-warm --reload` for frontend/API work that does not need a model preloaded.

## Pull requests

- Keep private audio, generated outputs, `.env`, certificates, and model weights out of commits.
- Add or update tests for behavior changes.
- Update public docs when configuration or API behavior changes.
- Verify `python -m build` and `pytest` before requesting review.
- Describe platform and hardware for inference-specific changes.

By contributing, you agree that your contribution is licensed under Apache-2.0.
