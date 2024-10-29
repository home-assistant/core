"""Tests for the TechnoVE integration."""

from unittest.mock import MagicMock

from technove import TechnoVEConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a successful setup entry and unload."""

    init_integration.add_to_hass(hass)
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_async_setup_connection_error(
    hass: HomeAssistant,
    mock_technove: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a connection error after setup."""
    mock_technove.update.side_effect = TechnoVEConnectionError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
