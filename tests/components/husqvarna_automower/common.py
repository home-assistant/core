"""Husqvarna Automwoer common helpers for tests."""
from unittest.mock import patch

from homeassistant.components.husqvarna_automower.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import mower_data
from .const import TEST_CLIENT_ID, TEST_CLIENT_SECRET


async def setup_platform(hass: HomeAssistant, mock_config_entry, side_effect=None):
    """Set up the Husqvarna Automower platform."""

    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            TEST_CLIENT_ID,
            TEST_CLIENT_SECRET,
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
        ),
    )

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.husqvarna_automower.coordinator.AutomowerDataUpdateCoordinator._async_update_data",
        return_value=mower_data,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
