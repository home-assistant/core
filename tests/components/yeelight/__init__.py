"""Tests for the Yeelight integration."""
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from async_upnp_client.search import SsdpSearchListener
from async_upnp_client.utils import CaseInsensitiveDict
from yeelight import BulbException, BulbType
from yeelight.main import _MODEL_SPECS

from homeassistant.components import zeroconf
from homeassistant.components.yeelight import (
    CONF_MODE_MUSIC,
    CONF_NIGHTLIGHT_SWITCH_TYPE,
    CONF_SAVE_ON_CHANGE,
    DOMAIN,
    NIGHTLIGHT_SWITCH_TYPE_LIGHT,
    YeelightScanner,
    scanner,
)
from homeassistant.const import CONF_DEVICES, CONF_ID, CONF_NAME
from homeassistant.core import callback

FAIL_TO_BIND_IP = "1.2.3.4"

IP_ADDRESS = "192.168.1.239"
MODEL = "color"
ID = "0x000000000015243f"
FW_VER = "18"

CAPABILITIES = {
    "id": ID,
    "model": MODEL,
    "fw_ver": FW_VER,
    "location": f"yeelight://{IP_ADDRESS}",
    "support": "get_prop set_default set_power toggle set_bright start_cf stop_cf"
    " set_scene cron_add cron_get cron_del set_ct_abx set_rgb",
    "name": "",
}

ID_DECIMAL = f"{int(ID, 16):08d}"

ZEROCONF_DATA = zeroconf.ZeroconfServiceInfo(
    host=IP_ADDRESS,
    addresses=[IP_ADDRESS],
    port=54321,
    hostname=f"yeelink-light-strip1_miio{ID_DECIMAL}.local.",
    type="_miio._udp.local.",
    name=f"yeelink-light-strip1_miio{ID_DECIMAL}._miio._udp.local.",
    properties={"epoch": "1", "mac": "000000000000"},
)

NAME = "name"
SHORT_ID = hex(int("0x000000000015243f", 16))
UNIQUE_NAME = f"yeelight_{MODEL}_{SHORT_ID}"
UNIQUE_FRIENDLY_NAME = f"Yeelight {MODEL.title()} {SHORT_ID}"

MODULE = "homeassistant.components.yeelight"
MODULE_CONFIG_FLOW = f"{MODULE}.config_flow"

PROPERTIES = {
    "power": "on",
    "main_power": "on",
    "bright": "50",
    "ct": "4000",
    "rgb": "16711680",
    "hue": "100",
    "sat": "35",
    "color_mode": "1",
    "flowing": "0",
    "bg_power": "on",
    "bg_lmode": "1",
    "bg_flowing": "0",
    "bg_ct": "5000",
    "bg_bright": "80",
    "bg_rgb": "65280",
    "bg_hue": "200",
    "bg_sat": "70",
    "nl_br": "23",
    "active_mode": "0",
    "current_brightness": "30",
}

ENTITY_BINARY_SENSOR_TEMPLATE = "binary_sensor.{}_nightlight"
ENTITY_BINARY_SENSOR = ENTITY_BINARY_SENSOR_TEMPLATE.format(UNIQUE_NAME)
ENTITY_LIGHT = f"light.{UNIQUE_NAME}"
ENTITY_NIGHTLIGHT = f"light.{UNIQUE_NAME}_nightlight"
ENTITY_AMBILIGHT = f"light.{UNIQUE_NAME}_ambilight"

YAML_CONFIGURATION = {
    DOMAIN: {
        CONF_DEVICES: {
            IP_ADDRESS: {
                CONF_NAME: NAME,
                CONF_NIGHTLIGHT_SWITCH_TYPE: NIGHTLIGHT_SWITCH_TYPE_LIGHT,
                CONF_MODE_MUSIC: True,
                CONF_SAVE_ON_CHANGE: True,
            }
        }
    }
}

CONFIG_ENTRY_DATA = {CONF_ID: ID}


class MockAsyncBulb:
    """A mock for yeelight.aio.AsyncBulb."""

    def __init__(self, model, bulb_type, cannot_connect):
        """Init the mock."""
        self.model = model
        self.bulb_type = bulb_type
        self._async_callback = None
        self._cannot_connect = cannot_connect

    async def async_listen(self, callback):
        """Mock the listener."""
        if self._cannot_connect:
            raise BulbException
        self._async_callback = callback

    async def async_stop_listening(self):
        """Drop the listener."""
        self._async_callback = None

    def set_capabilities(self, capabilities):
        """Mock setting capabilities."""
        self.capabilities = capabilities


def _mocked_bulb(cannot_connect=False):
    bulb = MockAsyncBulb(MODEL, BulbType.Color, cannot_connect)
    type(bulb).async_get_properties = AsyncMock(
        side_effect=BulbException if cannot_connect else None
    )
    type(bulb).get_properties = MagicMock(
        side_effect=BulbException if cannot_connect else None
    )
    type(bulb).get_model_specs = MagicMock(return_value=_MODEL_SPECS[MODEL])
    bulb.capabilities = CAPABILITIES.copy()
    bulb.available = True
    bulb.last_properties = PROPERTIES.copy()
    bulb.music_mode = False
    bulb.async_get_properties = AsyncMock()
    bulb.async_update = AsyncMock()
    bulb.async_turn_on = AsyncMock()
    bulb.async_turn_off = AsyncMock()
    bulb.async_set_brightness = AsyncMock()
    bulb.async_set_color_temp = AsyncMock()
    bulb.async_set_hsv = AsyncMock()
    bulb.async_set_rgb = AsyncMock()
    bulb.async_start_flow = AsyncMock()
    bulb.async_stop_flow = AsyncMock()
    bulb.async_set_power_mode = AsyncMock()
    bulb.async_set_scene = AsyncMock()
    bulb.async_set_default = AsyncMock()
    bulb.async_start_music = AsyncMock()
    return bulb


def _patched_ssdp_listener(info: CaseInsensitiveDict, *args, **kwargs):
    listener = SsdpSearchListener(*args, **kwargs)

    async def _async_callback(*_):
        if kwargs["source"][0] == FAIL_TO_BIND_IP:
            raise OSError
        await listener.async_connect_callback()

    @callback
    def _async_search(*_):
        if info:
            asyncio.create_task(listener.async_callback(info))

    listener.async_start = _async_callback
    listener.async_search = _async_search
    return listener


def _patch_discovery(no_device=False, capabilities=None):
    YeelightScanner._scanner = None  # Clear class scanner to reset hass

    def _generate_fake_ssdp_listener(*args, **kwargs):
        info = None
        if not no_device:
            info = capabilities or CAPABILITIES
        return _patched_ssdp_listener(info, *args, **kwargs)

    return patch(
        "homeassistant.components.yeelight.scanner.SsdpSearchListener",
        new=_generate_fake_ssdp_listener,
    )


def _patch_discovery_interval():
    return patch.object(scanner, "DISCOVERY_SEARCH_INTERVAL", timedelta(seconds=0))


def _patch_discovery_timeout():
    return patch.object(scanner, "DISCOVERY_TIMEOUT", 0.0001)
