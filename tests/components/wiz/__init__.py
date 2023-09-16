"""Tests for the WiZ Platform integration."""

from collections.abc import Callable
from contextlib import contextmanager
from copy import deepcopy
import json
from unittest.mock import AsyncMock, MagicMock, patch

from pywizlight import SCENES, BulbType, PilotParser, wizlight
from pywizlight.bulblibrary import BulbClass, Features, KelvinRange
from pywizlight.discovery import DiscoveredBulb

from homeassistant.components.wiz.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

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
FAKE_DUAL_HEAD_RGBWW_BULB = BulbType(
    bulb_type=BulbClass.RGB,
    name="ESP01_DHRGB_03",
    features=Features(
        color=True, color_tmp=True, effect=True, brightness=True, dual_head=True
    ),
    kelvin_range=KelvinRange(2700, 6500),
    fw_version="1.0.0",
    white_channels=2,
    white_to_color_ratio=80,
)
FAKE_RGBWW_BULB = BulbType(
    bulb_type=BulbClass.RGB,
    name="ESP01_SHRGB_03",
    features=Features(
        color=True, color_tmp=True, effect=True, brightness=True, dual_head=False
    ),
    kelvin_range=KelvinRange(2700, 6500),
    fw_version="1.0.0",
    white_channels=2,
    white_to_color_ratio=80,
)
FAKE_RGBW_BULB = BulbType(
    bulb_type=BulbClass.RGB,
    name="ESP01_SHRGB_03",
    features=Features(
        color=True, color_tmp=True, effect=True, brightness=True, dual_head=False
    ),
    kelvin_range=KelvinRange(2700, 6500),
    fw_version="1.0.0",
    white_channels=1,
    white_to_color_ratio=80,
)
FAKE_DIMMABLE_BULB = BulbType(
    bulb_type=BulbClass.DW,
    name="ESP01_DW_03",
    features=Features(
        color=False, color_tmp=False, effect=True, brightness=True, dual_head=False
    ),
    kelvin_range=KelvinRange(2700, 6500),
    fw_version="1.0.0",
    white_channels=1,
    white_to_color_ratio=80,
)
FAKE_TURNABLE_BULB = BulbType(
    bulb_type=BulbClass.TW,
    name="ESP01_TW_03",
    features=Features(
        color=False, color_tmp=True, effect=True, brightness=True, dual_head=False
    ),
    kelvin_range=KelvinRange(2700, 6500),
    fw_version="1.0.0",
    white_channels=1,
    white_to_color_ratio=80,
)
FAKE_SOCKET = BulbType(
    bulb_type=BulbClass.SOCKET,
    name="ESP01_SOCKET_03",
    features=Features(
        color=False, color_tmp=False, effect=False, brightness=False, dual_head=False
    ),
    kelvin_range=KelvinRange(2700, 6500),
    fw_version="1.0.0",
    white_channels=2,
    white_to_color_ratio=80,
)
FAKE_SOCKET_WITH_POWER_MONITORING = BulbType(
    bulb_type=BulbClass.SOCKET,
    name="ESP25_SOCKET_01",
    features=Features(
        color=False, color_tmp=False, effect=False, brightness=False, dual_head=False
    ),
    kelvin_range=KelvinRange(2700, 6500),
    fw_version="1.26.2",
    white_channels=2,
    white_to_color_ratio=80,
)
FAKE_OLD_FIRMWARE_DIMMABLE_BULB = BulbType(
    bulb_type=BulbClass.DW,
    name=None,
    features=Features(
        color=False, color_tmp=False, effect=True, brightness=True, dual_head=False
    ),
    kelvin_range=None,
    fw_version="1.8.0",
    white_channels=1,
    white_to_color_ratio=80,
)


async def setup_integration(hass: HomeAssistant) -> MockConfigEntry:
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
    bulb = MagicMock(auto_spec=wizlight, name="Mocked wizlight")

    async def _save_setup_callback(callback: Callable) -> None:
        bulb.push_callback = callback

    bulb.getBulbConfig = AsyncMock(return_value=device or FAKE_BULB_CONFIG)
    bulb.getExtendedWhiteRange = AsyncMock(
        return_value=extended_white_range or FAKE_EXTENDED_WHITE_RANGE
    )
    bulb.getMac = AsyncMock(return_value=FAKE_MAC)
    bulb.turn_on = AsyncMock()
    bulb.get_power = AsyncMock(return_value=None)
    bulb.turn_off = AsyncMock()
    bulb.power_monitoring = False
    bulb.updateState = AsyncMock(return_value=FAKE_STATE)
    bulb.getSupportedScenes = AsyncMock(return_value=list(SCENES.values()))
    bulb.start_push = AsyncMock(side_effect=_save_setup_callback)
    bulb.async_close = AsyncMock()
    bulb.set_speed = AsyncMock()
    bulb.set_ratio = AsyncMock()
    bulb.diagnostics = {
        "mocked": "mocked",
        "roomId": 123,
        "homeId": 34,
    }
    bulb.state = FAKE_STATE
    bulb.mac = FAKE_MAC
    bulb.bulbtype = bulb_type or FAKE_DIMMABLE_BULB
    bulb.get_bulbtype = AsyncMock(return_value=bulb_type or FAKE_DIMMABLE_BULB)

    return bulb


def _patch_wizlight(device=None, extended_white_range=None, bulb_type=None):
    @contextmanager
    def _patcher():
        bulb = device or _mocked_wizlight(device, extended_white_range, bulb_type)
        with patch("homeassistant.components.wiz.wizlight", return_value=bulb), patch(
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


async def async_setup_integration(
    hass, wizlight=None, device=None, extended_white_range=None, bulb_type=None
):
    """Set up the integration with a mock device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_MAC,
        data={CONF_HOST: FAKE_IP},
    )
    entry.add_to_hass(hass)
    bulb = wizlight or _mocked_wizlight(device, extended_white_range, bulb_type)
    with _patch_discovery(), _patch_wizlight(device=bulb):
        await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()
    return bulb, entry


async def async_push_update(hass, device, params):
    """Push an update to the device."""
    device.state = PilotParser(params)
    device.status = params.get("state")
    device.push_callback(device.state)
    await hass.async_block_till_done()
