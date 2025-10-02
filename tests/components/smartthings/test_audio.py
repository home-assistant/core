"""Tests for SmartThings audio helper."""

from __future__ import annotations

import io
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit
import wave

import pytest

from homeassistant.components.smartthings.audio import (
    MAX_DURATION_SECONDS,
    MAX_STORED_ENTRIES,
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


class _FakeProcess:
    """Async subprocess stand-in that provides communicate."""

    def __init__(self, stdout: bytes, stderr: bytes, returncode: int) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr


def _build_wav(
    duration_seconds: float = 1.0,
    *,
    sample_rate: int = PCM_SAMPLE_RATE,
    sample_width: int = PCM_SAMPLE_WIDTH,
    channels: int = PCM_CHANNELS,
) -> bytes:
    """Generate a silent PCM WAV blob for testing."""
    frame_count = int(sample_rate * duration_seconds)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00" * frame_count * sample_width * channels)
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
        ) as mock_get_url,
        pytest.raises(SmartThingsAudioError),
    ):
        await manager.async_prepare_notification("https://example.com/source.mp3")

    assert mock_get_url.called
    # Stored entry should be cleaned up after failure so subsequent requests
    # don't leak memory or serve stale audio.
    assert not manager._entries


async def test_audio_view_returns_404_for_unknown_token(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Unknown tokens should return 404."""

    await async_get_audio_manager(hass)
    client = await hass_client_no_auth()
    response = await client.get("/api/smartthings/audio/invalid-token.pcm")
    assert response.status == 404


@pytest.mark.asyncio
async def test_prepare_notification_raises_when_transcode_empty(
    hass: HomeAssistant,
) -> None:
    """Transcoding empty audio results in an error."""

    hass.config.external_url = "https://example.com"
    manager = await async_get_audio_manager(hass)

    with (
        patch.object(manager, "_transcode_to_pcm", AsyncMock(return_value=(b"", 0.0))),
        pytest.raises(SmartThingsAudioError, match="Converted audio is empty"),
    ):
        await manager.async_prepare_notification("https://example.com/source.mp3")


@pytest.mark.asyncio
async def test_prepare_notification_warns_when_duration_exceeds_max(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Warn when transcoded audio exceeds the SmartThings duration limit."""

    hass.config.external_url = "https://example.com"
    manager = await async_get_audio_manager(hass)

    wav_bytes = _build_wav(duration_seconds=MAX_DURATION_SECONDS + 1)
    caplog.set_level(logging.WARNING)

    with patch.object(
        manager,
        "_transcode_to_pcm",
        AsyncMock(return_value=(wav_bytes, MAX_DURATION_SECONDS + 1.0)),
    ):
        await manager.async_prepare_notification("https://example.com/source.mp3")

    assert any("exceeds" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_prepare_notification_evicts_old_entries(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ensure cached entries are evicted when exceeding the maximum."""

    hass.config.external_url = "https://example.com"
    manager = await async_get_audio_manager(hass)

    wav_bytes = _build_wav()
    caplog.set_level(logging.DEBUG)

    with patch.object(
        manager,
        "_transcode_to_pcm",
        AsyncMock(return_value=(wav_bytes, 1.0)),
    ):
        for _ in range(MAX_STORED_ENTRIES + 2):
            await manager.async_prepare_notification("https://example.com/source.mp3")

    assert len(manager._entries) == MAX_STORED_ENTRIES
    assert any(
        "Dropped expired SmartThings audio token" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_transcode_to_pcm_handles_missing_ffmpeg(
    hass: HomeAssistant,
) -> None:
    """Raise friendly error when ffmpeg is unavailable."""

    manager = await async_get_audio_manager(hass)

    with (
        patch(
            "homeassistant.components.smartthings.audio.ffmpeg.get_ffmpeg_manager",
            return_value=SimpleNamespace(binary="ffmpeg"),
        ),
        patch(
            "homeassistant.components.smartthings.audio.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError,
        ),
        pytest.raises(SmartThingsAudioError, match="FFmpeg is required"),
    ):
        await manager._transcode_to_pcm("https://example.com/source.mp3")


@pytest.mark.asyncio
async def test_transcode_to_pcm_handles_process_failure(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Raise when ffmpeg reports an error."""

    manager = await async_get_audio_manager(hass)
    caplog.set_level(logging.ERROR)

    fake_process = _FakeProcess(stdout=b"", stderr=b"boom", returncode=1)

    with (
        patch(
            "homeassistant.components.smartthings.audio.ffmpeg.get_ffmpeg_manager",
            return_value=SimpleNamespace(binary="ffmpeg"),
        ),
        patch(
            "homeassistant.components.smartthings.audio.asyncio.create_subprocess_exec",
            AsyncMock(return_value=fake_process),
        ),
        pytest.raises(SmartThingsAudioError, match="Unable to convert"),
    ):
        await manager._transcode_to_pcm("https://example.com/source.mp3")

    assert any("FFmpeg failed" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_transcode_to_pcm_returns_empty_audio(
    hass: HomeAssistant,
) -> None:
    """Return empty payload when ffmpeg produced nothing."""

    manager = await async_get_audio_manager(hass)
    fake_process = _FakeProcess(stdout=b"", stderr=b"", returncode=0)

    with (
        patch(
            "homeassistant.components.smartthings.audio.ffmpeg.get_ffmpeg_manager",
            return_value=SimpleNamespace(binary="ffmpeg"),
        ),
        patch(
            "homeassistant.components.smartthings.audio.asyncio.create_subprocess_exec",
            AsyncMock(return_value=fake_process),
        ) as mock_exec,
    ):
        pcm, duration = await manager._transcode_to_pcm(
            "https://example.com/source.mp3"
        )

    assert pcm == b""
    assert duration == 0.0
    mock_exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_transcode_to_pcm_logs_unexpected_format(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Log debug output when ffmpeg output format differs from expected PCM."""

    manager = await async_get_audio_manager(hass)
    caplog.set_level(logging.DEBUG)

    wav_bytes = _build_wav(sample_rate=44100)
    fake_process = _FakeProcess(stdout=wav_bytes, stderr=b"", returncode=0)

    with (
        patch(
            "homeassistant.components.smartthings.audio.ffmpeg.get_ffmpeg_manager",
            return_value=SimpleNamespace(binary="ffmpeg"),
        ),
        patch(
            "homeassistant.components.smartthings.audio.asyncio.create_subprocess_exec",
            AsyncMock(return_value=fake_process),
        ),
    ):
        pcm, duration = await manager._transcode_to_pcm(
            "https://example.com/source.mp3"
        )

    assert pcm == wav_bytes
    assert duration > 0
    assert any("unexpected format" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_transcode_to_pcm_invalid_wav(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Raise when ffmpeg output cannot be parsed as a WAV file."""

    manager = await async_get_audio_manager(hass)
    caplog.set_level(logging.ERROR)

    fake_process = _FakeProcess(stdout=b"notwav", stderr=b"", returncode=0)

    with (
        patch(
            "homeassistant.components.smartthings.audio.ffmpeg.get_ffmpeg_manager",
            return_value=SimpleNamespace(binary="ffmpeg"),
        ),
        patch(
            "homeassistant.components.smartthings.audio.asyncio.create_subprocess_exec",
            AsyncMock(return_value=fake_process),
        ),
        pytest.raises(SmartThingsAudioError, match="Unable to convert"),
    ):
        await manager._transcode_to_pcm("https://example.com/source.mp3")

    assert any("not a valid PCM WAV" in record.message for record in caplog.records)
