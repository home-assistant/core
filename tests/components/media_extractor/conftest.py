"""The tests for Media Extractor integration."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.media_extractor import DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service
from tests.components.media_extractor import MockYoutubeDL
from tests.components.media_extractor.const import AUDIO_QUERY


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant):
    """Set up the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})


@pytest.fixture(autouse=True)
async def setup_media_player(hass: HomeAssistant) -> None:
    """Set up the demo media player."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()


@pytest.fixture
def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track calls to a mock service."""
    return async_mock_service(hass, "media_player", "play_media")


@pytest.fixture(name="mock_youtube_dl")
async def setup_mock_yt_dlp(hass: HomeAssistant) -> MockYoutubeDL:
    """Mock YoutubeDL."""
    mock = MockYoutubeDL({})
    with patch("homeassistant.components.media_extractor.YoutubeDL", return_value=mock):
        yield mock


@pytest.fixture(name="empty_media_extractor_config")
def empty_media_extractor_config() -> dict[str, Any]:
    """Return base media extractor config."""
    return {DOMAIN: {}}


@pytest.fixture(name="audio_media_extractor_config")
def audio_media_extractor_config() -> dict[str, Any]:
    """Media extractor config for audio."""
    return {DOMAIN: {"default_query": AUDIO_QUERY}}
