"""The tests for the demo tts component."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_mock_service

from homeassistant.components.demo import DOMAIN
from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.tts import (
    DOMAIN as TTS_DOMAIN,
    TextToSpeechService,
    TextToSpeechServiceArgument,
    async_get_media_source_audio,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ENTITY_ID = "tts.demo_tts"


@pytest.fixture
def tts_only() -> Generator[None]:
    """Enable only the tts platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.TTS],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_config_entry(
    hass: HomeAssistant, tts_only: None, mock_tts_cache_dir: Path
) -> None:
    """Set up demo component from config entry."""
    assert await async_setup_component(hass, "homeassistant", {})
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_speak(hass: HomeAssistant) -> None:
    """Test the demo entity returns the demo audio."""
    calls = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)

    await hass.services.async_call(
        TTS_DOMAIN,
        TextToSpeechService.SPEAK,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            TextToSpeechServiceArgument.MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            TextToSpeechServiceArgument.MESSAGE: "There is someone at the door.",
        },
        blocking=True,
    )

    assert len(calls) == 1
    extension, data = await async_get_media_source_audio(
        hass, calls[0].data["media_content_id"]
    )
    assert extension == "mp3"
    assert data
