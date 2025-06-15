"""Tests for the Airthings integration."""

from unittest.mock import patch

from airthings import Airthings

from homeassistant.components.airthings import CONF_SECRET
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_DATA = {
    CONF_ID: "client_id",
    CONF_SECRET: "secret",
}


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    airthings_client: Airthings,
) -> None:
    """Fixture for setting up the component."""
    with (
        patch(
            "homeassistant.components.airthings.Airthings",
            return_value=airthings_client,
        ),
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
