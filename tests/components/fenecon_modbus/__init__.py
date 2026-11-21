"""Tests for the Fenecon Modbus integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant

HOST = "192.168.0.20"
SERIAL = "12345"


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
