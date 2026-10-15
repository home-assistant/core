"""Tests for the Profalux Neosol integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_PORT = "/dev/serial/by-id/usb-Profalux_Neosol_dongle-if00"
MOCK_SERIAL = "0012ABCD"


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the integration under test."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
