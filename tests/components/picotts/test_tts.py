"""Test for picoTTS."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch
import wave

import pytest

from homeassistant.components import picotts
from homeassistant.components.picotts.tts import DEFAULT_LANG, PicoTTSEntity
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def _setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the integration via a config entry."""
    entry = MockConfigEntry(domain=picotts.DOMAIN, data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.asyncio
async def test_setup_creates_tts_entity(hass: HomeAssistant) -> None:
    """Config entry setup should create the TTS entity."""
    # Patch NanoTTS so entity construction doesn't touch real backend
    with patch("homeassistant.components.picotts.tts.NanoTTS", autospec=True):
        await _setup_integration(hass)

    state = hass.states.get("tts.picotts")
    assert state is not None, "Expected tts.picotts entity to exist"
    assert state.name == "PicoTTS"


@pytest.mark.asyncio
async def test_async_get_tts_audio_returns_valid_wav(hass: HomeAssistant) -> None:
    """Ensure async_get_tts_audio returns a valid WAV file."""
    nano = MagicMock()
    nano.speak.return_value = b"\x00\x01" * 200  # fake PCM16 mono samples

    with patch("homeassistant.components.picotts.tts.NanoTTS", return_value=nano):
        await _setup_integration(hass)
        entity = PicoTTSEntity()

        content_type, data = await entity.async_get_tts_audio(
            message="hello",
            language="en-US",
            options={},
        )

    assert content_type == "wav"
    assert isinstance(data, (bytes, bytearray))

    # Validate WAV structure using Python's wave module
    with wave.open(io.BytesIO(data), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 16000
        assert wav_file.getnframes() == 200


@pytest.mark.asyncio
async def test_language_fallback_to_default(hass: HomeAssistant) -> None:
    """Unsupported language should fall back to DEFAULT_LANG when calling NanoTTS."""
    nano = MagicMock()
    nano.speak.return_value = b"\x00\x01" * 50

    with patch("homeassistant.components.picotts.tts.NanoTTS", return_value=nano):
        await _setup_integration(hass)

        entity = PicoTTSEntity()

        await entity.async_get_tts_audio(
            message="hello",
            language="xx-YY",  # unsupported
            options={"speed": "1.1", "pitch": "1.2", "volume": "1.3"},
        )

    # Ensure voice fell back to DEFAULT_LANG
    kwargs = nano.speak.call_args.kwargs
    assert kwargs["voice"] == DEFAULT_LANG
    assert kwargs["speed"] == 1.1
    assert kwargs["pitch"] == 1.2
    assert kwargs["volume"] == 1.3
