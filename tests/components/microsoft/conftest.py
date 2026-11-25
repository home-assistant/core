"""Common fixtures for the Microsoft Text-to-Speech tests."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.microsoft.const import (
    CONF_CONTOUR,
    CONF_GENDER,
    CONF_PITCH,
    CONF_RATE,
    CONF_VOLUME,
    DOMAIN,
)
from homeassistant.components.tts import CONF_LANG
from homeassistant.const import CONF_API_KEY, CONF_REGION, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config


@pytest.fixture(autouse=True)
def tts_mutagen_mock_fixture_autouse(tts_mutagen_mock: MagicMock) -> None:
    """Mock writing tags."""


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir: Path) -> None:
    """Mock the TTS cache dir with empty dir."""


@pytest.fixture(autouse=True)
async def setup_internal_url(hass: HomeAssistant) -> None:
    """Set up internal url."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.microsoft.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_tts_translator() -> Generator[MagicMock]:
    """Mock the Microsoft text-to-speech translator."""
    with patch(
        "pycsspeechtts.pycsspeechtts.TTSTranslator", autospec=True
    ) as mock_translator:
        mock_translator.return_value.speak.return_value = b"audio"
        yield mock_translator


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Microsoft Text-to-Speech config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Microsoft Text-to-Speech",
        entry_id="01KAB5VHQ8J6Q4WZ3CEY7B9K2D",
        data={
            CONF_API_KEY: "test-api-key",
            CONF_REGION: "westeurope",
            CONF_LANG: "en-gb",
            CONF_GENDER: "female",
            CONF_TYPE: "AbbiNeural",
        },
        options={
            CONF_RATE: 10,
            CONF_VOLUME: -10,
            CONF_PITCH: "high",
            CONF_CONTOUR: "(0%,+20Hz)",
        },
    )
