"""Tests for the WiLight component."""

from pywilight.const import DOMAIN

from homeassistant.components import ssdp
from homeassistant.components.ssdp import (
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_MODEL_NUMBER,
    ATTR_UPNP_SERIAL,
)
from homeassistant.components.wilight.config_flow import (
    CONF_MODEL_NAME,
    CONF_SERIAL_NUMBER,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

HOST = "127.0.0.1"
WILIGHT_ID = "000000000099"
SSDP_LOCATION = "http://127.0.0.1/"
UPNP_MANUFACTURER = "All Automacao Ltda"
UPNP_MODEL_NAME_P_B = "WiLight 0102001800010009-10010010"
UPNP_MODEL_NAME_DIMMER = "WiLight 0100001700020009-10010010"
UPNP_MODEL_NAME_COLOR = "WiLight 0107001800020009-11010"
UPNP_MODEL_NAME_LIGHT_FAN = "WiLight 0104001800010009-10"
UPNP_MODEL_NAME_COVER = "WiLight 0103001800010009-10"
UPNP_MODEL_NAME_SWITCH = "WiLight 0105001900010011-00000000000010"
UPNP_MODEL_NUMBER = "123456789012345678901234567890123456"
UPNP_SERIAL = "000000000099"
UPNP_MAC_ADDRESS = "5C:CF:7F:8B:CA:56"
UPNP_MANUFACTURER_NOT_WILIGHT = "Test"
CONF_COMPONENTS = "components"

MOCK_SSDP_DISCOVERY_INFO_P_B = ssdp.SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location=SSDP_LOCATION,
    upnp={
        ATTR_UPNP_MANUFACTURER: UPNP_MANUFACTURER,
        ATTR_UPNP_MODEL_NAME: UPNP_MODEL_NAME_P_B,
        ATTR_UPNP_MODEL_NUMBER: UPNP_MODEL_NUMBER,
        ATTR_UPNP_SERIAL: UPNP_SERIAL,
    },
)

MOCK_SSDP_DISCOVERY_INFO_WRONG_MANUFACTURER = ssdp.SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location=SSDP_LOCATION,
    upnp={
        ATTR_UPNP_MANUFACTURER: UPNP_MANUFACTURER_NOT_WILIGHT,
        ATTR_UPNP_MODEL_NAME: UPNP_MODEL_NAME_P_B,
        ATTR_UPNP_MODEL_NUMBER: UPNP_MODEL_NUMBER,
        ATTR_UPNP_SERIAL: ATTR_UPNP_SERIAL,
    },
)

MOCK_SSDP_DISCOVERY_INFO_MISSING_MANUFACTURER = ssdp.SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location=SSDP_LOCATION,
    upnp={
        ATTR_UPNP_MODEL_NAME: UPNP_MODEL_NAME_P_B,
        ATTR_UPNP_MODEL_NUMBER: UPNP_MODEL_NUMBER,
        ATTR_UPNP_SERIAL: ATTR_UPNP_SERIAL,
    },
)


async def setup_integration(
    hass: HomeAssistant,
) -> MockConfigEntry:
    """Mock ConfigEntry in Home Assistant."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WILIGHT_ID,
        data={
            CONF_HOST: HOST,
            CONF_SERIAL_NUMBER: UPNP_SERIAL,
            CONF_MODEL_NAME: UPNP_MODEL_NAME_P_B,
        },
    )

    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
