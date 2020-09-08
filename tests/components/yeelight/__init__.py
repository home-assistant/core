"""Tests for the Yeelight integration."""
from yeelight import BulbType
from yeelight.main import _MODEL_SPECS

from homeassistant.components.yeelight import (
    CONF_MODE_MUSIC,
    CONF_NIGHTLIGHT_SWITCH_TYPE,
    CONF_SAVE_ON_CHANGE,
    DOMAIN,
    NIGHTLIGHT_SWITCH_TYPE_LIGHT,
)
from homeassistant.const import CONF_DEVICES, CONF_ID, CONF_NAME

from tests.async_mock import MagicMock, patch

IP_ADDRESS = "192.168.1.239"
MODEL = "color"
ID = "0x000000000015243f"
FW_VER = "18"

CAPABILITIES = {
    "id": ID,
    "model": MODEL,
    "fw_ver": FW_VER,
    "support": "get_prop set_default set_power toggle set_bright start_cf stop_cf"
    " set_scene cron_add cron_get cron_del set_ct_abx set_rgb",
    "name": "",
}

NAME = f"yeelight_{MODEL}_{ID}"

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
    "bg_rgb": "16711680",
    "nl_br": "23",
    "active_mode": "0",
    "current_brightness": "30",
}

ENTITY_BINARY_SENSOR = f"binary_sensor.{NAME}_nightlight"
ENTITY_LIGHT = f"light.{NAME}"
ENTITY_NIGHTLIGHT = f"light.{NAME}_nightlight"

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

CONFIG_ENTRY_DATA = {
    CONF_ID: ID,
}


def _mocked_bulb(cannot_connect=False):
    bulb = MagicMock()
    type(bulb).get_capabilities = MagicMock(
        return_value=None if cannot_connect else CAPABILITIES
    )
    type(bulb).get_model_specs = MagicMock(return_value=_MODEL_SPECS[MODEL])

    bulb.capabilities = CAPABILITIES
    bulb.model = MODEL
    bulb.bulb_type = BulbType.Color
    bulb.last_properties = PROPERTIES
    bulb.music_mode = False

    return bulb


def _patch_discovery(prefix, no_device=False):
    def _mocked_discovery(timeout=2, interface=False):
        if no_device:
            return []
        return [{"ip": IP_ADDRESS, "port": 55443, "capabilities": CAPABILITIES}]

    return patch(f"{prefix}.discover_bulbs", side_effect=_mocked_discovery)
