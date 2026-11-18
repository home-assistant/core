"""Tests for the WATERCryst integration setup."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.watercryst.coordinator import WatercrystUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("mock_api_client")
async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test standard setup and unloading of the config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert type(mock_config_entry.runtime_data) is WatercrystUpdateCoordinator

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
