"""Command-line entry point for NarraTTS."""
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the NarraTTS web studio and API")
    parser.add_argument("--host", help="Bind host (default: TTS_HOST or 127.0.0.1)")
    parser.add_argument("--port", type=int, help="Bind port (default: TTS_PORT or 8765)")
    parser.add_argument("--reload", action="store_true", help="Reload when source files change")
    parser.add_argument("--no-warm", action="store_true", help="Do not preload the default model")
    args = parser.parse_args()

    from .config import settings

    if args.host:
        settings.host = args.host
    if args.port:
        settings.port = args.port
    if args.no_warm:
        settings.warm_on_start = False

    import uvicorn

    uvicorn.run(
        "service.app:app",
        host=settings.host,
        port=settings.port,
        reload=args.reload,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
