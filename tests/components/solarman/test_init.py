from unittest.mock import patch, AsyncMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr

from homeassistant.components.solarman.const import DOMAIN

from tests.common import MockConfigEntry, load_json_object_fixture

@pytest.mark.parametrize(
    "device_fixture", ["SP-2W-EU"], indirect=True
)
async def test_load_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up and removing a config entry."""

    # Add the mock config entry to Home Assistant
    mock_config_entry.add_to_hass(hass)
    
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.data["sn"])}
    )
    
    with patch(
        "homeassistant.components.solarman.coordinator.Solarman.fetch_data",
        new_callable=AsyncMock,
        return_value={"current": 0, "voltage": 0},
    ), patch(
        "homeassistant.components.solarman.config_flow.Solarman.get_config",
        new_callable=AsyncMock,
        return_value=load_json_object_fixture("SP-2W-EU/config.json", DOMAIN)
    ):
        # Set up the integration using the config entry
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        
        # Wait for all background tasks to complete
        await hass.async_block_till_done()

        # Verify the config entry is successfully loaded
        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Unload the integration
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify the config entry is properly unloaded
        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "device_fixture", ["SP-2W-EU"], indirect=True
)
async def test_load_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
):
    """Test setup failure."""
    # Patch the get_config function to simulate a timeout error
    with patch(
        "homeassistant.components.solarman.config_flow.Solarman.get_config",
        side_effect=TimeoutError,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify the config entry enters retry state due to failure
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
