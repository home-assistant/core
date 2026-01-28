from unittest.mock import patch, AsyncMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntryState

from tests.common import MockConfigEntry

@pytest.mark.parametrize(
    "device_fixture", ["SolidFlex/PowerFlex2000"], indirect=True
)
async def test_load_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up and removing a config entry."""
    # Patch the indevolt component to prevent actual network calls
    with patch(
        "homeassistant.components.indevolt.indevolt.Indevolt.fetch_data",
        new_callable=AsyncMock,
        return_value={0: "SolidFlex/PowerFlex2000"},
    ):
        # Add the mock config entry to Home Assistant
        mock_config_entry.add_to_hass(hass)

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
    "device_fixture", ["SolidFlex/PowerFlex2000"], indirect=True
)
async def test_load_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
):
    """Test setup failure."""
    # Patch the get_config function to simulate a timeout error
    with patch(
        "homeassistant.components.indevolt.indevolt.Indevolt.fetch_data",
        side_effect=TimeoutError,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify the config entry enters retry state due to failure
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
