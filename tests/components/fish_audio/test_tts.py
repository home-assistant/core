"""Tests for the Fish Audio TTS entity."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from fishaudio import RateLimitError
from fishaudio.exceptions import ServerError
import pytest

from homeassistant.components import tts
from homeassistant.components.fish_audio.const import CONF_BACKEND
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import MockConfigEntry, async_mock_service
from tests.components.tts.common import retrieve_media
from tests.typing import ClientSessionGenerator


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
async def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Mock media player calls."""
    return async_mock_service(hass, MP_DOMAIN, SERVICE_PLAY_MEDIA)


async def test_tts_service_success(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test TTS service with successful audio generation."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the TTS entity
    entity = hass.data[tts.DOMAIN].get_entity("tts.test_voice_test_voice")
    assert entity is not None

    # Test the TTS audio generation
    extension, data = await entity.async_get_tts_audio(
        message="Hello world",
        language="en",
        options={},
    )

    # Verify the result
    assert extension == "mp3"
    assert data == b"fake_audio_data"

    # Verify the client was called
    mock_fishaudio_client.tts.convert.assert_called_once()


async def test_tts_rate_limited(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test TTS service with rate limit error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the TTS entity
    entity = hass.data[tts.DOMAIN].get_entity("tts.test_voice_test_voice")
    assert entity is not None

    # Make tts.convert() fail with rate limit error
    mock_fishaudio_client.tts.convert = AsyncMock(
        side_effect=RateLimitError(429, "Rate limited")
    )

    # Test that the error is raised
    with pytest.raises(HomeAssistantError, match="Rate limited"):
        await entity.async_get_tts_audio(
            message="Hello world",
            language="en",
            options={},
        )

    # Verify the client was called
    mock_fishaudio_client.tts.convert.assert_called_once()


async def test_tts_missing_voice_id(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test TTS service raises ServiceValidationError when voice_id is missing."""
    # Create a config entry with no voice_id
    entry = MockConfigEntry(
        domain="fish_audio",
        data={"api_key": "test-key"},
        unique_id="test_user",
        subentries_data=[
            ConfigSubentryData(
                data={CONF_BACKEND: "s1"},  # Missing CONF_VOICE_ID
                subentry_type="tts",
                title="Test Voice",
                subentry_id="test-sub-id",
                unique_id="test-voice",
            )
        ],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get the TTS entity
    entity = hass.data[tts.DOMAIN].get_entity("tts.test_voice_test_voice")
    assert entity is not None

    # Test that the error is raised
    with pytest.raises(ServiceValidationError, match="Voice ID not configured"):
        await entity.async_get_tts_audio(
            message="Hello world",
            language="en",
            options={},
        )


async def test_tts_supported_languages(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test TTS entity supported languages."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the TTS entity
    entity = hass.data[tts.DOMAIN].get_entity("tts.test_voice_test_voice")
    assert entity is not None

    # Verify supported languages
    assert entity.supported_languages == [
        "Any",
        "en",
        "zh",
        "de",
        "ja",
        "ar",
        "fr",
        "es",
        "ko",
    ]


# Service-level integration tests


async def test_tts_service_speak(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
) -> None:
    """Test TTS speak service call."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        {
            ATTR_ENTITY_ID: "tts.test_voice_test_voice",
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "Hello world",
        },
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )


async def test_tts_service_speak_with_language(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
) -> None:
    """Test TTS speak service call with language parameter."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        {
            ATTR_ENTITY_ID: "tts.test_voice_test_voice",
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "Hola mundo",
            tts.ATTR_LANGUAGE: "es",
        },
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )


async def test_tts_service_speak_server_error(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
) -> None:
    """Test TTS speak service call with server error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the client from runtime_data and make it fail with ServerError
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None
    mock_fishaudio_client.tts.convert = AsyncMock(
        side_effect=ServerError(500, "Internal server error")
    )

    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        {
            ATTR_ENTITY_ID: "tts.test_voice_test_voice",
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "Test server error",
        },
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.INTERNAL_SERVER_ERROR
    )


async def test_tts_service_speak_rate_limit_error(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
) -> None:
    """Test TTS speak service call with rate limit error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the client from runtime_data and make it fail with RateLimitError
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None
    mock_fishaudio_client.tts.convert = AsyncMock(
        side_effect=RateLimitError(429, "Rate limit exceeded")
    )

    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        {
            ATTR_ENTITY_ID: "tts.test_voice_test_voice",
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "Test rate limit error",
        },
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.INTERNAL_SERVER_ERROR
    )
