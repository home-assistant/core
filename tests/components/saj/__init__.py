"""Tests for the saj integration."""

from homeassistant.components.saj.const import CONNECTION_TYPES
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TYPE, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_USER_INPUT_ETHERNET = {
    CONF_HOST: "192.168.1.100",
    CONF_TYPE: CONNECTION_TYPES[0],
}

MOCK_USER_INPUT_WIFI = {
    CONF_HOST: "192.168.1.100",
    CONF_TYPE: CONNECTION_TYPES[1],
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "password",
}

MOCK_SERIAL_NUMBER = "TEST123456789"


async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
