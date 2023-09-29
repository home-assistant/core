"""Common fixtures for the Wyoming tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import stt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import STT_INFO, TTS_INFO

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.wyoming.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def stt_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Create a config entry."""
    entry = MockConfigEntry(
        domain="wyoming",
        data={
            "host": "1.2.3.4",
            "port": 1234,
        },
        title="Test ASR",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def tts_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Create a config entry."""
    entry = MockConfigEntry(
        domain="wyoming",
        data={
            "host": "1.2.3.4",
            "port": 1234,
        },
        title="Test TTS",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def init_wyoming_stt(hass: HomeAssistant, stt_config_entry: ConfigEntry):
    """Initialize Wyoming STT."""
    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=STT_INFO,
    ):
        await hass.config_entries.async_setup(stt_config_entry.entry_id)


@pytest.fixture
async def init_wyoming_tts(hass: HomeAssistant, tts_config_entry: ConfigEntry):
    """Initialize Wyoming TTS."""
    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=TTS_INFO,
    ):
        await hass.config_entries.async_setup(tts_config_entry.entry_id)


@pytest.fixture
def metadata(hass: HomeAssistant) -> stt.SpeechMetadata:
    """Get default STT metadata."""
    return stt.SpeechMetadata(
        language=hass.config.language,
        format=stt.AudioFormats.WAV,
        codec=stt.AudioCodecs.PCM,
        bit_rate=stt.AudioBitRates.BITRATE_16,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
    )
