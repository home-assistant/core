"""Test the AirPatrol integration setup."""

from unittest.mock import AsyncMock

from homeassistant.components.airpatrol.coordinator import (
    AirPatrolDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_authentication: AsyncMock,
    mock_api_response: AsyncMock,
    get_data,
) -> None:
    """Test loading and unloading the config entry."""
    # Add the config entry to hass first
    mock_config_entry.add_to_hass(hass)

    mock_api_response.return_value = get_data()
    mock_api_authentication.return_value = mock_api_response

    # Load the config entry
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert isinstance(mock_config_entry.runtime_data, AirPatrolDataUpdateCoordinator)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
