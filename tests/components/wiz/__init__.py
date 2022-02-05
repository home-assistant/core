"""Tests for the WiZ Platform integration."""

import json

from homeassistant.components.wiz.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

FAKE_BULB_CONFIG = json.loads(
    '{"method":"getSystemConfig","env":"pro","result":\
    {"mac":"ABCABCABCABC",\
    "homeId":653906,\
    "roomId":989983,\
    "moduleName":"ESP_0711_STR",\
    "fwVersion":"1.21.0",\
    "groupId":0,"drvConf":[20,2],\
    "ewf":[255,0,255,255,0,0,0],\
    "ewfHex":"ff00ffff000000",\
    "ping":0}}'
)

REAL_BULB_CONFIG = json.loads(
    '{"method":"getSystemConfig","env":"pro","result":\
    {"mac":"ABCABCABCABC",\
    "homeId":653906,\
    "roomId":989983,\
    "moduleName":"ESP01_SHRGB_03",\
    "fwVersion":"1.21.0",\
    "groupId":0,"drvConf":[20,2],\
    "ewf":[255,0,255,255,0,0,0],\
    "ewfHex":"ff00ffff000000",\
    "ping":0}}'
)

TEST_SYSTEM_INFO = {"id": "ABCABCABCABC", "name": "Test Bulb"}

TEST_CONNECTION = {CONF_IP_ADDRESS: "1.1.1.1", CONF_NAME: "Test Bulb"}


async def setup_integration(
    hass: HomeAssistantType,
) -> MockConfigEntry:
    """Mock ConfigEntry in Home Assistant."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SYSTEM_INFO["id"],
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_NAME: TEST_SYSTEM_INFO["name"],
        },
    )

    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
