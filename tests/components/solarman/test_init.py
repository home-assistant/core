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
    hass: HomeAssistant, 
    mock_config_entry: MockConfigEntry,
    mock_solarman: AsyncMock,
) -> None:
    """Test setting up and removing a config entry."""

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
    "device_fixture", ["SP-2W-EU"], indirect=True
)
async def test_load_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_solarman
):
    """Test setup failure."""
    mock_solarman.fetch_data.side_effect = TimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the config entry enters retry state due to failure
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
