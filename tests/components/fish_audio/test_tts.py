"""Tests for the Fish Audio TTS entity."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fishaudio import FishAudioError, RateLimitError
import pytest

from homeassistant.components.fish_audio.const import CONF_BACKEND
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_component import DATA_INSTANCES

from tests.common import MockConfigEntry


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
    entity = hass.data[DATA_INSTANCES]["tts"].get_entity("tts.test_voice_test_voice")
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
    entity = hass.data[DATA_INSTANCES]["tts"].get_entity("tts.test_voice_test_voice")
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


async def test_tts_api_error(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test TTS service with generic API error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the TTS entity
    entity = hass.data[DATA_INSTANCES]["tts"].get_entity("tts.test_voice_test_voice")
    assert entity is not None

    # Make tts.convert() fail with API error
    mock_fishaudio_client.tts.convert = AsyncMock(
        side_effect=FishAudioError("API error")
    )

    # Test that the error is raised
    with pytest.raises(HomeAssistantError, match="TTS request failed"):
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
    entity = hass.data[DATA_INSTANCES]["tts"].get_entity("tts.test_voice_test_voice")
    assert entity is not None

    # Test that the error is raised
    with pytest.raises(ServiceValidationError, match="Voice ID not configured"):
        await entity.async_get_tts_audio(
            message="Hello world",
            language="en",
            options={},
        )
