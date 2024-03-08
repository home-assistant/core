"""Common fixtures for the Wyoming tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import stt
from homeassistant.components.wyoming import DOMAIN
from homeassistant.components.wyoming.devices import SatelliteDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import SATELLITE_INFO, STT_INFO, TTS_INFO, WAKE_WORD_INFO

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir):
    """Mock the TTS cache dir with empty dir."""
    return mock_tts_cache_dir


@pytest.fixture(autouse=True)
async def init_components(hass: HomeAssistant):
    """Set up required components."""
    assert await async_setup_component(hass, "homeassistant", {})


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
def wake_word_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Create a config entry."""
    entry = MockConfigEntry(
        domain="wyoming",
        data={
            "host": "1.2.3.4",
            "port": 1234,
        },
        title="Test Wake Word",
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
async def init_wyoming_wake_word(
    hass: HomeAssistant, wake_word_config_entry: ConfigEntry
):
    """Initialize Wyoming Wake Word."""
    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=WAKE_WORD_INFO,
    ):
        await hass.config_entries.async_setup(wake_word_config_entry.entry_id)


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


@pytest.fixture
def satellite_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Create a config entry."""
    entry = MockConfigEntry(
        domain="wyoming",
        data={
            "host": "1.2.3.4",
            "port": 1234,
        },
        title="Test Satellite",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def init_satellite(hass: HomeAssistant, satellite_config_entry: ConfigEntry):
    """Initialize Wyoming satellite."""
    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.WyomingSatellite.run"
        ) as _run_mock,
    ):
        # _run_mock: satellite task does not actually run
        await hass.config_entries.async_setup(satellite_config_entry.entry_id)


@pytest.fixture
async def satellite_device(
    hass: HomeAssistant, init_satellite, satellite_config_entry: ConfigEntry
) -> SatelliteDevice:
    """Get a satellite device fixture."""
    return hass.data[DOMAIN][satellite_config_entry.entry_id].satellite.device
