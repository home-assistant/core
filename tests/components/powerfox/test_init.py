"""Test the Powerfox init module."""

from __future__ import annotations

from unittest.mock import AsyncMock

from powerfox import PowerfoxConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Powerfox configuration entry not ready."""
    mock_powerfox_client.all_devices.side_effect = PowerfoxConnectionError
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
