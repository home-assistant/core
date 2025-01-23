"""Tests for the ElevenLabs TTS entity."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    mock_async_client: MagicMock,
    mock_entry: MockConfigEntry,
) -> None:
    """Test entry setup without any exceptions."""
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    assert mock_entry.state == ConfigEntryState.LOADED
    # Unload
    await hass.config_entries.async_unload(mock_entry.entry_id)
    assert mock_entry.state == ConfigEntryState.NOT_LOADED


async def test_setup_connect_error(
    hass: HomeAssistant,
    mock_async_client_connect_error: MagicMock,
    mock_entry: MockConfigEntry,
) -> None:
    """Test entry setup with a connection error."""
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    # Ensure is not ready
    assert mock_entry.state == ConfigEntryState.SETUP_RETRY
