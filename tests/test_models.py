from pydantic import ValidationError

from service.models import VoiceCloneRequest, VoiceDesignRequest


def test_voice_clone_requires_reference() -> None:
    try:
        VoiceCloneRequest(text="hello", voice_ids=[])
    except ValidationError:
        return
    raise AssertionError("empty voice_ids must be rejected")


def test_voice_design_requires_meaningful_instruction() -> None:
    try:
        VoiceDesignRequest(text="hello", instruct="low")
    except ValidationError:
        return
    raise AssertionError("short voice instructions must be rejected")
