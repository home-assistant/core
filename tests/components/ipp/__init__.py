"""Tests for the IPP integration."""
import os

from homeassistant.components.ipp.const import CONF_BASE_PATH, CONF_UUID, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_TYPE,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

ATTR_HOSTNAME = "hostname"
ATTR_PROPERTIES = "properties"

IPP_ZEROCONF_SERVICE_TYPE = "_ipp._tcp.local."
IPPS_ZEROCONF_SERVICE_TYPE = "_ipps._tcp.local."

ZEROCONF_NAME = "EPSON XP-6000 Series"
ZEROCONF_HOST = "192.168.1.31"
ZEROCONF_HOSTNAME = "EPSON123456.local."
ZEROCONF_PORT = 631


MOCK_USER_INPUT = {
    CONF_HOST: "192.168.1.31",
    CONF_PORT: 361,
    CONF_SSL: False,
    CONF_VERIFY_SSL: False,
    CONF_BASE_PATH: "/ipp/print",
}

MOCK_ZEROCONF_IPP_SERVICE_INFO = {
    CONF_TYPE: IPP_ZEROCONF_SERVICE_TYPE,
    CONF_NAME: f"{ZEROCONF_NAME}.{IPP_ZEROCONF_SERVICE_TYPE}",
    CONF_HOST: ZEROCONF_HOST,
    ATTR_HOSTNAME: ZEROCONF_HOSTNAME,
    CONF_PORT: ZEROCONF_PORT,
    ATTR_PROPERTIES: {"rp": "ipp/print"},
}

MOCK_ZEROCONF_IPPS_SERVICE_INFO = {
    CONF_TYPE: IPPS_ZEROCONF_SERVICE_TYPE,
    CONF_NAME: f"{ZEROCONF_NAME}.{IPPS_ZEROCONF_SERVICE_TYPE}",
    CONF_HOST: ZEROCONF_HOST,
    ATTR_HOSTNAME: ZEROCONF_HOSTNAME,
    CONF_PORT: ZEROCONF_PORT,
    ATTR_PROPERTIES: {"rp": "ipp/print"},
}


def load_fixture_binary(filename):
    """Load a binary fixture."""
    path = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", filename)
    with open(path, "rb") as fptr:
        return fptr.read()


async def init_integration(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the IPP integration in Home Assistant."""
    fixture = "ipp/get-printer-attributes.bin"
    aioclient_mock.post(
        "http://192.168.1.31:631/ipp/print",
        content=load_fixture_binary(fixture),
        headers={"Content-Type": "application/ipp"},
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="cfe92100-67c4-11d4-a45f-f8d027761251",
        data={
            CONF_HOST: "192.168.1.31",
            CONF_PORT: 631,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_BASE_PATH: "/ipp/print",
            CONF_UUID: "cfe92100-67c4-11d4-a45f-f8d027761251",
        },
    )

    entry.add_to_hass(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
