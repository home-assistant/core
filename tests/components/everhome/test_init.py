"""Tests for the everHome/EcoTracker integration."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_platform

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_everhome_client")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_connection_failed(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when the device is unreachable."""
    mock_everhome_client.async_update.return_value = False
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
