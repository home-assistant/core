"""Tests for SmartThings audio helper."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit
import wave

import pytest

from homeassistant.components.smartthings.audio import (
    PCM_CHANNELS,
    PCM_MIME,
    PCM_SAMPLE_RATE,
    PCM_SAMPLE_WIDTH,
    SmartThingsAudioError,
    async_get_audio_manager,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError

from tests.typing import ClientSessionGenerator


def _build_wav(duration_seconds: float = 1.0) -> bytes:
    """Generate a silent PCM WAV blob for testing."""
    frame_count = int(PCM_SAMPLE_RATE * duration_seconds)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(PCM_CHANNELS)
        wav_file.setsampwidth(PCM_SAMPLE_WIDTH)
        wav_file.setframerate(PCM_SAMPLE_RATE)
        wav_file.writeframes(b"\x00" * frame_count * PCM_SAMPLE_WIDTH * PCM_CHANNELS)
    return buffer.getvalue()


async def test_prepare_notification_creates_url(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Ensure PCM proxy URLs are generated and served."""

    hass.config.external_url = "https://example.com"
    manager = await async_get_audio_manager(hass)

    wav_bytes = _build_wav()

    with patch.object(
        manager, "_transcode_to_pcm", AsyncMock(return_value=(wav_bytes, 1.0))
    ):
        url = await manager.async_prepare_notification("https://example.com/source.mp3")

    parsed = urlsplit(url)
    assert parsed.path.endswith(".pcm")
    assert not parsed.query

    client = await hass_client_no_auth()
    response = await client.get(parsed.path)
    assert response.status == 200
    assert response.headers["Content-Type"] == PCM_MIME
    assert response.headers["Cache-Control"] == "no-store"
    body = await response.read()
    assert body == wav_bytes


@pytest.mark.asyncio
async def test_prepare_notification_uses_internal_url_when_external_missing(
    hass: HomeAssistant,
) -> None:
    """Fallback to the internal URL if no external URL is available."""

    hass.config.external_url = None
    hass.config.internal_url = "http://homeassistant.local:8123"
    manager = await async_get_audio_manager(hass)

    wav_bytes = _build_wav()

    with patch.object(
        manager, "_transcode_to_pcm", AsyncMock(return_value=(wav_bytes, 1.0))
    ):
        url = await manager.async_prepare_notification("https://example.com/source.mp3")

    parsed = urlsplit(url)
    assert parsed.scheme == "http"
    assert parsed.netloc == "homeassistant.local:8123"
    assert parsed.path.endswith(".pcm")


@pytest.mark.asyncio
async def test_prepare_notification_requires_accessible_url(
    hass: HomeAssistant,
) -> None:
    """Fail if neither external nor internal URLs are available."""

    hass.config.external_url = None
    hass.config.internal_url = None
    manager = await async_get_audio_manager(hass)

    wav_bytes = _build_wav()

    with (
        patch.object(
            manager, "_transcode_to_pcm", AsyncMock(return_value=(wav_bytes, 1.0))
        ),
        patch(
            "homeassistant.components.smartthings.audio.get_url",
            side_effect=NoURLAvailableError,
        ),
        pytest.raises(SmartThingsAudioError),
    ):
        await manager.async_prepare_notification("https://example.com/source.mp3")


async def test_audio_view_returns_404_for_unknown_token(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Unknown tokens should return 404."""

    await async_get_audio_manager(hass)
    client = await hass_client_no_auth()
    response = await client.get("/api/smartthings/audio/invalid-token.pcm")
    assert response.status == 404
