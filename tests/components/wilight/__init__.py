"""Tests for the WiLight component."""
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_MODEL_NUMBER,
    ATTR_UPNP_SERIAL,
)
from homeassistant.components.wilight.config_flow import (
    CONF_MODEL_NAME,
    CONF_SERIAL_NUMBER,
)
from homeassistant.components.wilight.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

HOST = "127.0.0.1"
WILIGHT_ID = "WL000000000099"
SSDP_LOCATION = "http://127.0.0.1/"
UPNP_MANUFACTURER = "All Automacao Ltda"
UPNP_MODEL_NAME = "WiLight 0102001800010009-10010010"
UPNP_MODEL_NUMBER = "123456789012345678901234567890123456"
UPNP_SERIAL = "000000000099"
UPNP_MANUFACTURER_NOT_WILIGHT = "Test"
UPNP_MODEL_NAME_NOT_SUPPORTED = "WiLight 0105001800020009-00000000002510"

CONF_COMPONENTS = "components"

MOCK_SSDP_DISCOVERY_INFO = {
    ATTR_SSDP_LOCATION: SSDP_LOCATION,
    ATTR_UPNP_MANUFACTURER: UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME: UPNP_MODEL_NAME,
    ATTR_UPNP_MODEL_NUMBER: UPNP_MODEL_NUMBER,
    ATTR_UPNP_SERIAL: UPNP_SERIAL,
}

MOCK_SSDP_DISCOVERY_INFO_1 = {
    ATTR_SSDP_LOCATION: SSDP_LOCATION,
    ATTR_UPNP_MANUFACTURER: UPNP_MANUFACTURER_NOT_WILIGHT,
    ATTR_UPNP_MODEL_NAME: UPNP_MODEL_NAME,
    ATTR_UPNP_MODEL_NUMBER: UPNP_MODEL_NUMBER,
    ATTR_UPNP_SERIAL: ATTR_UPNP_SERIAL,
}

MOCK_SSDP_DISCOVERY_INFO_2 = {
    ATTR_SSDP_LOCATION: SSDP_LOCATION,
    ATTR_UPNP_MANUFACTURER: UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME: UPNP_MODEL_NAME_NOT_SUPPORTED,
    ATTR_UPNP_MODEL_NUMBER: UPNP_MODEL_NUMBER,
    ATTR_UPNP_SERIAL: ATTR_UPNP_SERIAL,
}


async def setup_integration(hass: HomeAssistantType,) -> MockConfigEntry:
    """Set up the WiLight integration in Home Assistant."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WILIGHT_ID,
        data={
            CONF_HOST: HOST,
            CONF_SERIAL_NUMBER: UPNP_SERIAL,
            CONF_MODEL_NAME: UPNP_MODEL_NAME,
        },
    )

    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
