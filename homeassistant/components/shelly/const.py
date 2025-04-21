"""Constants for the Shelly integration."""

from __future__ import annotations

from enum import StrEnum
from logging import Logger, getLogger
import re
from typing import Final

from aioshelly.const import (
    MODEL_BULB,
    MODEL_BULB_RGBW,
    MODEL_BUTTON1,
    MODEL_BUTTON1_V2,
    MODEL_DIMMER,
    MODEL_DIMMER_2,
    MODEL_DUO,
    MODEL_DW,
    MODEL_DW_2,
    MODEL_GAS,
    MODEL_HT,
    MODEL_MOTION,
    MODEL_MOTION_2,
    MODEL_RGBW2,
    MODEL_VALVE,
    MODEL_VINTAGE_V2,
    MODEL_WALL_DISPLAY,
    MODEL_WALL_DISPLAY_X2,
)

from homeassistant.components.number import NumberMode
from homeassistant.components.sensor import SensorDeviceClass

DOMAIN: Final = "shelly"

LOGGER: Logger = getLogger(__package__)

CONF_COAP_PORT: Final = "coap_port"
FIRMWARE_PATTERN: Final = re.compile(r"^(\d{8})")

# max BLOCK light transition time in milliseconds (min=0)
BLOCK_MAX_TRANSITION_TIME_MS: Final = 5000

# min RPC light transition time in seconds (max=10800, limited by light entity to 6553)
RPC_MIN_TRANSITION_TIME_SEC = 0.5

RGBW_MODELS: Final = (
    MODEL_BULB,
    MODEL_RGBW2,
)

MOTION_MODELS: Final = (
    MODEL_MOTION,
    MODEL_MOTION_2,
)

MODELS_SUPPORTING_LIGHT_TRANSITION: Final = (
    MODEL_DUO,
    MODEL_BULB_RGBW,
    MODEL_DIMMER,
    MODEL_DIMMER_2,
    MODEL_RGBW2,
    MODEL_VINTAGE_V2,
)

MODELS_SUPPORTING_LIGHT_EFFECTS: Final = (
    MODEL_BULB,
    MODEL_BULB_RGBW,
    MODEL_RGBW2,
)

MODELS_WITH_WRONG_SLEEP_PERIOD: Final = (
    MODEL_DW,
    MODEL_DW_2,
    MODEL_HT,
)

# Bulbs that support white & color modes
DUAL_MODE_LIGHT_MODELS: Final = (
    MODEL_BULB,
    MODEL_BULB_RGBW,
)

# Refresh interval for REST sensors
REST_SENSORS_UPDATE_INTERVAL: Final = 60

# Refresh interval for RPC polling sensors
RPC_SENSORS_POLLING_INTERVAL: Final = 60

CONF_SLEEP_PERIOD: Final = "sleep_period"

# Multiplier used to calculate the "update_interval" for shelly devices.
UPDATE_PERIOD_MULTIPLIER: Final = 2.2

# Reconnect interval for GEN2 devices
RPC_RECONNECT_INTERVAL = 60

# Shelly Air - Maximum work hours before lamp replacement
SHAIR_MAX_WORK_HOURS: Final = 9000

# Map Shelly input events
INPUTS_EVENTS_DICT: Final = {
    "S": "single",
    "SS": "double",
    "SSS": "triple",
    "L": "long",
    "SL": "single_long",
    "LS": "long_single",
}

# List of battery devices that maintain a permanent WiFi connection
BATTERY_DEVICES_WITH_PERMANENT_CONNECTION: Final = [
    MODEL_MOTION,
    MODEL_MOTION_2,
    MODEL_VALVE,
]

# Button/Click events for Block & RPC devices
EVENT_SHELLY_CLICK: Final = "shelly.click"

SHELLY_EMIT_EVENT_PATTERN: Final = re.compile(
    r"(?:Shelly\s*\.\s*emitEvent\s*\(\s*[\"'`])(\w*)"
)

ATTR_CLICK_TYPE: Final = "click_type"
ATTR_CHANNEL: Final = "channel"
ATTR_DEVICE: Final = "device"
ATTR_GENERATION: Final = "generation"
CONF_SUBTYPE: Final = "subtype"
ATTR_BETA: Final = "beta"
CONF_OTA_BETA_CHANNEL: Final = "ota_beta_channel"

BASIC_INPUTS_EVENTS_TYPES: Final = {"single", "long"}

SHBTN_INPUTS_EVENTS_TYPES: Final = {"single", "double", "triple", "long"}

RPC_INPUTS_EVENTS_TYPES: Final = {
    "btn_down",
    "btn_up",
    "single_push",
    "double_push",
    "triple_push",
    "long_push",
}

BLOCK_INPUTS_EVENTS_TYPES: Final = {
    "single",
    "double",
    "triple",
    "long",
    "single_long",
    "long_single",
}

SHIX3_1_INPUTS_EVENTS_TYPES = BLOCK_INPUTS_EVENTS_TYPES

INPUTS_EVENTS_SUBTYPES: Final = {
    "button": 1,
    "button1": 1,
    "button2": 2,
    "button3": 3,
    "button4": 4,
}

SHBTN_MODELS: Final = [MODEL_BUTTON1, MODEL_BUTTON1_V2]

STANDARD_RGB_EFFECTS: Final = {
    0: "Off",
    1: "Meteor Shower",
    2: "Gradual Change",
    3: "Flash",
}

SHBLB_1_RGB_EFFECTS: Final = {
    0: "Off",
    1: "Meteor Shower",
    2: "Gradual Change",
    3: "Flash",
    4: "Breath",
    5: "On/Off Gradual",
    6: "Red/Green Change",
}

SHTRV_01_TEMPERATURE_SETTINGS: Final = {
    "min": 4,
    "max": 31,
    "step": 0.5,
    "default": 20.0,
}
RPC_THERMOSTAT_SETTINGS: Final = {
    "min": 5,
    "max": 35,
    "step": 0.5,
}

BLU_TRV_TEMPERATURE_SETTINGS: Final = {
    "min": 4,
    "max": 30,
    "step": 0.1,
    "default": 20.0,
}

# Kelvin value for colorTemp
KELVIN_MAX_VALUE: Final = 6500
KELVIN_MIN_VALUE_WHITE: Final = 2700
KELVIN_MIN_VALUE_COLOR: Final = 3000

# Sleep period
BLOCK_WRONG_SLEEP_PERIOD = 21600
BLOCK_EXPECTED_SLEEP_PERIOD = 43200

UPTIME_DEVIATION: Final = 60

# Time to wait before reloading entry upon device config change
ENTRY_RELOAD_COOLDOWN = 60

SHELLY_GAS_MODELS = [MODEL_GAS]

CONF_BLE_SCANNER_MODE = "ble_scanner_mode"


class BLEScannerMode(StrEnum):
    """BLE scanner mode."""

    DISABLED = "disabled"
    ACTIVE = "active"
    PASSIVE = "passive"


MAX_PUSH_UPDATE_FAILURES = 5
PUSH_UPDATE_ISSUE_ID = "push_update_{unique}"

NOT_CALIBRATED_ISSUE_ID = "not_calibrated_{unique}"

FIRMWARE_UNSUPPORTED_ISSUE_ID = "firmware_unsupported_{unique}"

BLE_SCANNER_FIRMWARE_UNSUPPORTED_ISSUE_ID = "ble_scanner_firmware_unsupported_{unique}"

GAS_VALVE_OPEN_STATES = ("opening", "opened")

OTA_BEGIN = "ota_begin"
OTA_ERROR = "ota_error"
OTA_PROGRESS = "ota_progress"
OTA_SUCCESS = "ota_success"

GEN1_RELEASE_URL = "https://shelly-api-docs.shelly.cloud/gen1/#changelog"
GEN2_RELEASE_URL = "https://shelly-api-docs.shelly.cloud/gen2/changelog/"
GEN2_BETA_RELEASE_URL = f"{GEN2_RELEASE_URL}#unreleased"
DEVICES_WITHOUT_FIRMWARE_CHANGELOG = (
    MODEL_WALL_DISPLAY,
    MODEL_WALL_DISPLAY_X2,
    MODEL_MOTION,
    MODEL_MOTION_2,
    MODEL_VALVE,
)

CONF_GEN = "gen"

VIRTUAL_COMPONENTS_MAP = {
    "binary_sensor": {"types": ["boolean"], "modes": ["label"]},
    "number": {"types": ["number"], "modes": ["field", "slider"]},
    "select": {"types": ["enum"], "modes": ["dropdown"]},
    "sensor": {"types": ["enum", "number", "text"], "modes": ["label"]},
    "switch": {"types": ["boolean"], "modes": ["toggle"]},
    "text": {"types": ["text"], "modes": ["field"]},
}

VIRTUAL_NUMBER_MODE_MAP = {
    "field": NumberMode.BOX,
    "slider": NumberMode.SLIDER,
}


API_WS_URL = "/api/shelly/ws"

COMPONENT_ID_PATTERN = re.compile(r"[a-z\d]+:\d+")

ROLE_TO_DEVICE_CLASS_MAP = {
    "current_humidity": SensorDeviceClass.HUMIDITY,
    "current_temperature": SensorDeviceClass.TEMPERATURE,
}

# We want to check only the first 5 KB of the script if it contains emitEvent()
# so that the integration startup remains fast.
MAX_SCRIPT_SIZE = 5120
