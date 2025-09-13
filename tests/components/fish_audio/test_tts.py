"""Tests for the Fish Audio TTS entity."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.fish_audio.const import (
    CONF_API_KEY,
    CONF_BACKEND,
    CONF_VOICE_ID,
    DOMAIN,
)
import homeassistant.components.fish_audio.tts as tts_mod
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_tts_happy_path_builds_request_and_returns_audio(
    hass: HomeAssistant,
    mock_async_client: MagicMock,  # patched constructor => returns session double
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Entity builds TTSRequest, passes backend, and returns concatenated audio."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key123"},
        options={CONF_VOICE_ID: "voice-123", CONF_BACKEND: "s1"},
        title="Fish Audio",
    )

    session = mock_async_client.return_value
    entry.runtime_data = session

    captured: dict[str, object] = {}

    def fake_tts(*, request, backend):
        captured["request"] = request
        captured["backend"] = backend
        return [b"foo", b"bar"]

    session.tts = fake_tts

    async def inline_executor(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(hass, "async_add_executor_job", inline_executor)

    added: list = []

    # NOTE: sync callback (NOT async)!
    def add_entities(entities):
        added.extend(entities)

    await tts_mod.async_setup_entry(hass, entry, add_entities)
    assert len(added) == 1
    entity = added[0]

    # Attach hass so entity.async_get_tts_audio can call self.hass.async_add_executor_job
    entity.hass = hass

    assert entity.default_language == "en"
    assert "en" in entity.supported_languages

    audio_type, audio_bytes = await entity.async_get_tts_audio("Hello world", "en", {})
    assert audio_type == "mp3"
    assert audio_bytes == b"foobar"

    req = captured["request"]
    assert req.text == "Hello world"
    assert req.reference_id == "voice-123"
    assert captured["backend"] == "s1"


@pytest.mark.asyncio
async def test_tts_missing_voice_id_returns_none(
    hass: HomeAssistant,
    mock_async_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If voice_id is missing, entity returns None and does not call session.tts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key123"},
        options={CONF_BACKEND: "s1"},  # voice id intentionally missing
        title="Fish Audio",
    )
    session = mock_async_client.return_value
    entry.runtime_data = session

    session.tts = MagicMock()

    async def inline_executor(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(hass, "async_add_executor_job", inline_executor)

    added: list = []

    def add_entities(entities):
        added.extend(entities)

    await tts_mod.async_setup_entry(hass, entry, add_entities)
    assert len(added) == 1
    entity = added[0]
    entity.hass = hass  # attach hass

    result = await entity.async_get_tts_audio("Hello world", "en", {})
    assert result == (None, None)
    session.tts.assert_not_called()


@pytest.mark.asyncio
async def test_tts_missing_backend_returns_none(
    hass: HomeAssistant,
    mock_async_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If backend is missing, entity returns None and does not call session.tts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key123"},
        options={CONF_VOICE_ID: "voice-123"},  # backend intentionally missing
        title="Fish Audio",
    )
    session = mock_async_client.return_value
    entry.runtime_data = session

    session.tts = MagicMock()

    async def inline_executor(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(hass, "async_add_executor_job", inline_executor)

    added: list = []

    def add_entities(entities):
        added.extend(entities)

    await tts_mod.async_setup_entry(hass, entry, add_entities)
    assert len(added) == 1
    entity = added[0]
    entity.hass = hass  # attach hass

    result = await entity.async_get_tts_audio("Hello world", "en", {})
    assert result == (None, None)
    session.tts.assert_not_called()


@pytest.mark.asyncio
async def test_tts_api_failure_returns_none(
    hass: HomeAssistant,
    mock_async_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured correctly, but underlying API call fails -> return None (graceful)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key123"},
        options={CONF_VOICE_ID: "voice-xyz", CONF_BACKEND: "s1"},
        title="Fish Audio",
    )
    session = mock_async_client.return_value
    entry.runtime_data = session

    # Simulate API error from session.tts
    def boom(*, request, backend):
        raise RuntimeError("backend temporarily unavailable")

    session.tts = boom

    async def inline_executor(func, *args, **kwargs):
        # Mimic executor behavior: call the function and let its exception surface
        return func(*args, **kwargs)

    monkeypatch.setattr(hass, "async_add_executor_job", inline_executor)

    added: list = []

    def add_entities(entities):
        added.extend(entities)

    await tts_mod.async_setup_entry(hass, entry, add_entities)
    assert len(added) == 1
    entity = added[0]
    entity.hass = hass

    # Expect graceful handling (None) when API raises
    result = await entity.async_get_tts_audio("Hello!", "en", {})
    assert result == (None, None)
