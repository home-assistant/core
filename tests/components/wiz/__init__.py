"""Tests for the WiZ Platform integration."""

from contextlib import contextmanager
from copy import deepcopy
import json
from typing import Callable
from unittest.mock import AsyncMock, MagicMock, patch

from pywizlight import SCENES, BulbType, PilotParser, wizlight
from pywizlight.bulblibrary import FEATURE_MAP, BulbClass, KelvinRange
from pywizlight.discovery import DiscoveredBulb

from homeassistant.components.wiz.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

FAKE_STATE = PilotParser(
    {
        "mac": "a8bb50818e7c",
        "rssi": -55,
        "src": "hb",
        "mqttCd": 0,
        "ts": 1644425347,
        "state": True,
        "sceneId": 0,
        "r": 0,
        "g": 0,
        "b": 255,
        "c": 0,
        "w": 0,
        "dimming": 100,
    }
)
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
FAKE_RGBWW_BULB = BulbType(
    bulb_type=BulbClass.RGB,
    name="ESP01_SHRGB_03",
    features=FEATURE_MAP[BulbClass.RGB],
    kelvin_range=KelvinRange(2700, 6500),
    fw_version="1.0.0",
    white_channels=2,
    white_to_color_ratio=80,
)
FAKE_RGBW_BULB = BulbType(
    bulb_type=BulbClass.RGB,
    name="ESP01_SHRGB_03",
    features=FEATURE_MAP[BulbClass.RGB],
    kelvin_range=KelvinRange(2700, 6500),
    fw_version="1.0.0",
    white_channels=1,
    white_to_color_ratio=80,
)
FAKE_DIMMABLE_BULB = BulbType(
    bulb_type=BulbClass.DW,
    name="ESP01_DW_03",
    features=FEATURE_MAP[BulbClass.DW],
    kelvin_range=KelvinRange(2700, 6500),
    fw_version="1.0.0",
    white_channels=1,
    white_to_color_ratio=80,
)
FAKE_SOCKET = BulbType(
    bulb_type=BulbClass.SOCKET,
    name="ESP01_SOCKET_03",
    features=FEATURE_MAP[BulbClass.SOCKET],
    kelvin_range=KelvinRange(2700, 6500),
    fw_version="1.0.0",
    white_channels=2,
    white_to_color_ratio=80,
)


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


def _mocked_wizlight(device, extended_white_range, bulb_type) -> wizlight:
    bulb = MagicMock(auto_spec=wizlight)

    async def _save_setup_callback(callback: Callable) -> None:
        bulb.data_receive_callback = callback

    bulb.getBulbConfig = AsyncMock(return_value=device or FAKE_BULB_CONFIG)
    bulb.getExtendedWhiteRange = AsyncMock(
        return_value=extended_white_range or FAKE_EXTENDED_WHITE_RANGE
    )
    bulb.getMac = AsyncMock(return_value=FAKE_MAC)
    bulb.updateState = AsyncMock(return_value=FAKE_STATE)
    bulb.getSupportedScenes = AsyncMock(return_value=list(SCENES))
    bulb.start_push = AsyncMock(side_effect=_save_setup_callback)
    bulb.async_close = AsyncMock()
    bulb.state = FAKE_STATE
    bulb.mac = FAKE_MAC
    bulb.bulbtype = bulb_type or FAKE_DIMMABLE_BULB
    bulb.get_bulbtype = AsyncMock(return_value=bulb_type or FAKE_DIMMABLE_BULB)

    return bulb


def _patch_wizlight(device=None, extended_white_range=None, bulb_type=None):
    @contextmanager
    def _patcher():
        bulb = _mocked_wizlight(device, extended_white_range, bulb_type)
        with patch("homeassistant.components.wiz.wizlight", return_value=bulb,), patch(
            "homeassistant.components.wiz.config_flow.wizlight",
            return_value=bulb,
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
