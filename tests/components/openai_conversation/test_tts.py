"""Test TTS platform of OpenAI Conversation integration."""

from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
from openai import RateLimitError
import pytest

from homeassistant.components import tts
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_mock_service
from tests.components.tts.common import retrieve_media
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def tts_mutagen_mock_fixture_autouse(tts_mutagen_mock: MagicMock) -> None:
    """Mock writing tags."""


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir: Path) -> None:
    """Mock the TTS cache dir with empty dir."""


@pytest.fixture
async def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Mock media player calls."""
    return async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)


@pytest.fixture(autouse=True)
async def setup_internal_url(hass: HomeAssistant) -> None:
    """Set up internal url."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )


@pytest.mark.parametrize(
    "service_data",
    [
        {
            ATTR_ENTITY_ID: "tts.openai_tts",
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_OPTIONS: {},
        },
        {
            ATTR_ENTITY_ID: "tts.openai_tts",
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice2"},
        },
    ],
)
@pytest.mark.usefixtures("mock_init_component")
async def test_tts(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_create_speech: MagicMock,
    entity_registry: er.EntityRegistry,
    calls: list[ServiceCall],
    service_data: dict[str, Any],
) -> None:
    """Test text to speech generation."""
    entity_id = "tts.openai_tts"

    # Ensure entity is linked to the subentry
    entity_entry = entity_registry.async_get(entity_id)
    tts_entry = next(
        iter(
            entry
            for entry in mock_config_entry.subentries.values()
            if entry.subentry_type == "tts"
        )
    )
    assert entity_entry is not None
    assert entity_entry.config_entry_id == mock_config_entry.entry_id
    assert entity_entry.config_subentry_id == tts_entry.subentry_id

    # Mock the OpenAI response stream
    mock_create_speech.return_value = [b"mock aud", b"io data"]

    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )
    voice_id = service_data[tts.ATTR_OPTIONS].get(tts.ATTR_VOICE, "marin")
    mock_create_speech.assert_called_once_with(
        model="gpt-4o-mini-tts",
        voice=voice_id,
        input="There is a person at the front door.",
        instructions="",
        speed=1.0,
        response_format="mp3",
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_tts_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_create_speech: MagicMock,
    entity_registry: er.EntityRegistry,
    calls: list[ServiceCall],
) -> None:
    """Test exception handling during text to speech generation."""
    # Mock the OpenAI response stream
    mock_create_speech.side_effect = RateLimitError(
        response=httpx.Response(status_code=429, request=""),
        body=None,
        message=None,
    )

    service_data = {
        ATTR_ENTITY_ID: "tts.openai_tts",
        tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
        tts.ATTR_MESSAGE: "There is a person at the front door.",
        tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice1"},
    }

    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.INTERNAL_SERVER_ERROR
    )
    mock_create_speech.assert_called_once_with(
        model="gpt-4o-mini-tts",
        voice="voice1",
        input="There is a person at the front door.",
        instructions="",
        speed=1.0,
        response_format="mp3",
    )
