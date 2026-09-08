"""JSON extraction from model output, and the validate-then-retry wrapper."""

import pytest
from schemas import FairnessReport
from services import llm_service
from services.llm_service import LLMOutputError, parse_json_response, strip_fences


@pytest.mark.parametrize("raw", [
    '{"status": "ok", "flags": []}',
    '```json\n{"status": "ok", "flags": []}\n```',
    '```\n{"status": "ok", "flags": []}\n```',
    'Here is the JSON:\n{"status": "ok", "flags": []}\nHope that helps.',
])
def test_parses_json_through_fences_and_prose(raw):
    assert parse_json_response(raw) == {"status": "ok", "flags": []}


def test_strip_fences_leaves_bare_json_untouched():
    assert strip_fences('{"a": 1}') == '{"a": 1}'


def test_invalid_json_raises():
    with pytest.raises(LLMOutputError):
        parse_json_response("not json at all")


@pytest.mark.asyncio
async def test_json_chat_retries_once_then_succeeds(monkeypatch):
    """A first bad answer must be retried with the error fed back."""
    calls = []

    async def fake_chat(system, user, *, model, max_tokens=2048):
        calls.append(user)
        if len(calls) == 1:
            return "sorry, I can't do that"
        return '{"status": "ok", "flags": []}'

    monkeypatch.setattr(llm_service, "_chat", fake_chat)
    result = await llm_service._json_chat(
        "sys", "original prompt", model="m", schema=FairnessReport
    )
    assert result == {"status": "ok", "flags": []}
    assert len(calls) == 2
    assert "was rejected" in calls[1]
    assert "original prompt" in calls[1]


@pytest.mark.asyncio
async def test_json_chat_raises_after_the_retry(monkeypatch):
    async def always_bad(system, user, *, model, max_tokens=2048):
        return "still not json"

    monkeypatch.setattr(llm_service, "_chat", always_bad)
    with pytest.raises(LLMOutputError):
        await llm_service._json_chat("sys", "u", model="m", schema=FairnessReport)


@pytest.mark.asyncio
async def test_json_chat_rejects_a_wrong_shape(monkeypatch):
    """Valid JSON with the wrong shape must not reach the caller."""
    async def wrong_shape(system, user, *, model, max_tokens=2048):
        return '{"status": "definitely-not-a-valid-status"}'

    monkeypatch.setattr(llm_service, "_chat", wrong_shape)
    with pytest.raises(LLMOutputError):
        await llm_service._json_chat("sys", "u", model="m", schema=FairnessReport)


def test_model_tiers_default_to_current_ids(monkeypatch):
    """The shipped defaults, independent of any local .env or import order.

    Reading the live module globals made this test depend on whether `main`
    (and its `load_dotenv()`) had been imported first — a local .env pinning
    CLAUDE_MODEL silently changed the result.
    """
    import importlib

    for var in ("CLAUDE_MODEL", "CLAUDE_MODEL_FAST", "CLAUDE_MODEL_SMART"):
        monkeypatch.delenv(var, raising=False)
    reloaded = importlib.reload(llm_service)
    try:
        assert reloaded.FAST_MODEL == "claude-haiku-4-5"
        assert reloaded.SMART_MODEL == "claude-sonnet-5"
    finally:
        importlib.reload(llm_service)  # restore the env-configured module


def test_legacy_claude_model_override_still_applies(monkeypatch):
    """`CLAUDE_MODEL` is the documented back-compat override for the smart tier."""
    import importlib

    monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-5")
    monkeypatch.delenv("CLAUDE_MODEL_SMART", raising=False)
    reloaded = importlib.reload(llm_service)
    try:
        assert reloaded.SMART_MODEL == "claude-opus-5"
    finally:
        monkeypatch.undo()
        importlib.reload(llm_service)
