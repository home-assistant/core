"""Tests for the LibreHardwareMonitor integration."""

from homeassistant.components.librehardwaremonitor.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

VALID_CONFIG = {CONF_HOST: "192.168.0.20", CONF_PORT: 8085}


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the LibreHardwareMonitor integration in Home Assistant."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.20:8085",
        unique_id="192.168.0.20:8085",
        data=VALID_CONFIG,
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    return mock_entry
