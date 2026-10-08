"""Tests for the ElevenLabs TTS entity."""

from unittest.mock import MagicMock

from homeassistant.components.elevenlabs.const import CONF_VOICE
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
    assert mock_entry.state is ConfigEntryState.LOADED
    # Unload
    await hass.config_entries.async_unload(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_connect_error(
    hass: HomeAssistant,
    mock_async_client_connect_error: MagicMock,
    mock_entry: MockConfigEntry,
) -> None:
    """Test entry setup with a connection error."""
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    # Ensure is not ready
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_options_update_reloads_once(
    hass: HomeAssistant,
    mock_async_client: MagicMock,
    mock_entry: MockConfigEntry,
) -> None:
    """Test an options update reloads the entry once after earlier reloads."""
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.config_entries.async_reload(mock_entry.entry_id)
    await hass.config_entries.async_reload(mock_entry.entry_id)
    await hass.async_block_till_done()

    models_list = mock_async_client.return_value.models.list
    models_list.reset_mock()

    hass.config_entries.async_update_entry(
        mock_entry, options={**mock_entry.options, CONF_VOICE: "voice2"}
    )
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.LOADED
    assert models_list.await_count == 1
