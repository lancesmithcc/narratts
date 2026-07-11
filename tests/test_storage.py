from pathlib import Path

import pytest

from service import storage


def test_slugify() -> None:
    assert storage.slugify(" Warm Narrator! ") == "warm-narrator"


def test_voice_store_rejects_unknown_extension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(storage.settings, "voices_dir", tmp_path)
    voice_store = storage.VoiceStore()
    with pytest.raises(ValueError, match="Unsupported audio format"):
        voice_store.create(b"not audio", "sample.exe")
