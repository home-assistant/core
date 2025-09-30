"""Tests for SmartThings audio helper."""

from __future__ import annotations

import io
import sys
import types
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit
import wave

import pytest

# Provide minimal haffmpeg stub so ffmpeg imports succeed without installing dependency.
if "haffmpeg" not in sys.modules:
    haffmpeg_module = types.ModuleType("haffmpeg")
    haffmpeg_core_module = types.ModuleType("haffmpeg.core")
    haffmpeg_tools_module = types.ModuleType("haffmpeg.tools")

    class _StubHAFFmpeg:  # pragma: no cover - simple stub
        ...

    class _StubFFVersion:  # pragma: no cover - simple stub
        ...

    class _StubImageFrame:  # pragma: no cover - simple stub
        ...

    haffmpeg_core_module.HAFFmpeg = _StubHAFFmpeg
    haffmpeg_tools_module.IMAGE_JPEG = b""
    haffmpeg_tools_module.FFVersion = _StubFFVersion
    haffmpeg_tools_module.ImageFrame = _StubImageFrame
    haffmpeg_module.core = haffmpeg_core_module
    haffmpeg_module.tools = haffmpeg_tools_module
    sys.modules["haffmpeg"] = haffmpeg_module
    sys.modules["haffmpeg.core"] = haffmpeg_core_module
    sys.modules["haffmpeg.tools"] = haffmpeg_tools_module

from homeassistant.components.smartthings.audio import (
    PCM_CHANNELS,
    PCM_MIME,
    PCM_SAMPLE_RATE,
    PCM_SAMPLE_WIDTH,
    SmartThingsAudioError,
    async_get_audio_manager,
)
from homeassistant.core import HomeAssistant

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
async def test_prepare_notification_requires_external_url(
    hass: HomeAssistant,
) -> None:
    """External URL must be configured."""

    hass.config.external_url = None
    manager = await async_get_audio_manager(hass)

    wav_bytes = _build_wav()

    with (
        patch.object(
            manager, "_transcode_to_pcm", AsyncMock(return_value=(wav_bytes, 1.0))
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
