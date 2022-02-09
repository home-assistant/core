"""Tests for the WiZ Platform integration."""

from contextlib import contextmanager
from copy import deepcopy
import json
from unittest.mock import patch

from pywizlight.discovery import DiscoveredBulb

from homeassistant.components.wiz.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

FAKE_IP = "1.1.1.1"
FAKE_MAC = "ABCABCABCABC"
FAKE_BULB_CONFIG = {
    "method": "getSystemConfig",
    "env": "pro",
    "result": {
        "mac": FAKE_MAC,
        "homeId": 653906,
        "roomId": 989983,
        "moduleName": "ESP_0711_STR",
        "fwVersion": "1.21.0",
        "groupId": 0,
        "drvConf": [20, 2],
        "ewf": [255, 0, 255, 255, 0, 0, 0],
        "ewfHex": "ff00ffff000000",
        "ping": 0,
    },
}
FAKE_SOCKET_CONFIG = deepcopy(FAKE_BULB_CONFIG)
FAKE_SOCKET_CONFIG["result"]["moduleName"] = "ESP10_SOCKET_06"
FAKE_EXTENDED_WHITE_RANGE = [2200, 2700, 6500, 6500]
TEST_SYSTEM_INFO = {"id": FAKE_MAC, "name": "Test Bulb"}
TEST_CONNECTION = {CONF_HOST: "1.1.1.1"}
TEST_NO_IP = {CONF_HOST: "this is no IP input"}

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

TEST_CONNECTION = {CONF_HOST: "1.1.1.1", CONF_NAME: "Test Bulb"}


async def setup_integration(
    hass: HomeAssistantType,
) -> MockConfigEntry:
    """Mock ConfigEntry in Home Assistant."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SYSTEM_INFO["id"],
        data={
            CONF_HOST: "127.0.0.1",
            CONF_NAME: TEST_SYSTEM_INFO["name"],
        },
    )

    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


def _patch_wizlight(device=None, extended_white_range=None):
    @contextmanager
    def _patcher():
        with patch(
            "homeassistant.components.wiz.wizlight.getBulbConfig",
            return_value=device or FAKE_BULB_CONFIG,
        ), patch(
            "homeassistant.components.wiz.wizlight.getExtendedWhiteRange",
            return_value=extended_white_range or FAKE_EXTENDED_WHITE_RANGE,
        ), patch(
            "homeassistant.components.wiz.wizlight.getMac",
            return_value=FAKE_MAC,
        ):
            yield

    return _patcher()


def _patch_discovery():
    @contextmanager
    def _patcher():
        with patch(
            "homeassistant.components.wiz.discovery.find_wizlights",
            return_value=[DiscoveredBulb(FAKE_IP, FAKE_MAC)],
        ):
            yield

    return _patcher()
