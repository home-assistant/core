"""Tests for setting up the Junker integration."""

from unittest.mock import Mock

from homeassistant.components.junker.junker_api import JunkerError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_and_unload(
    hass: HomeAssistant,
    config_entry,
    mock_junker_client,
) -> None:
    """Test that the integration can be set up and unloaded."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry(
    hass: HomeAssistant, config_entry, client: Mock, mock_junker_client
) -> None:
    """Test the entry is retried when the calendar cannot be fetched."""
    client.async_get_collections.side_effect = JunkerError
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
