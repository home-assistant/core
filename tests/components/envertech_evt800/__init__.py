"""Tests for the Envertech EVT800 integration."""

from homeassistant.components.envertech_evt800.const import TYPE_TCP_SERVER_MODE
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DEVICE = {
    "manufacturer": "Envertech",
    "name": "EVT800",
    "type": "Inverter",
    "serial": 123456789,
    "sw_version": "1.0.0",
}

MOCK_USER_INPUT = {
    CONF_IP_ADDRESS: "1.1.1.1",
    CONF_PORT: 1234,
    CONF_TYPE: TYPE_TCP_SERVER_MODE,
}


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
