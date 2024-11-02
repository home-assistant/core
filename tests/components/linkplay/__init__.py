"""Tests for the LinkPlay integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

HOST = "10.0.0.150"
HOST_REENTRY = "10.0.0.66"
UUID = "FF31F09E-5001-FBDE-0546-2DBFFF31F09E"
NAME = "Smart Zone 1_54B9"


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
