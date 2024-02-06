"""Husqvarna Automwoer common helpers for tests."""
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from .conftest import mower_data


async def setup_platform(hass: HomeAssistant, mock_config_entry, side_effect=None):
    """Set up the Husqvarna Automower platform."""

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.husqvarna_automower.coordinator.AutomowerDataUpdateCoordinator._async_update_data",
        return_value=mower_data,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
