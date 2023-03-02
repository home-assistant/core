"""Constants for the Shelly integration."""
from __future__ import annotations

from logging import Logger, getLogger
import re
from typing import Final

from awesomeversion import AwesomeVersion

from homeassistant.backports.enum import StrEnum

DOMAIN: Final = "shelly"

LOGGER: Logger = getLogger(__package__)

DATA_CONFIG_ENTRY: Final = "config_entry"
CONF_COAP_PORT: Final = "coap_port"
DEFAULT_COAP_PORT: Final = 5683
FIRMWARE_PATTERN: Final = re.compile(r"^(\d{8})")

# Firmware 1.11.0 release date, this firmware supports light transition
LIGHT_TRANSITION_MIN_FIRMWARE_DATE: Final = 20210226

# max light transition time in milliseconds
MAX_TRANSITION_TIME: Final = 5000

RGBW_MODELS: Final = (
    "SHBLB-1",
    "SHRGBW2",
)

MODELS_SUPPORTING_LIGHT_TRANSITION: Final = (
    "SHBDUO-1",
    "SHCB-1",
    "SHDM-1",
    "SHDM-2",
    "SHRGBW2",
    "SHVIN-1",
)

MODELS_SUPPORTING_LIGHT_EFFECTS: Final = (
    "SHBLB-1",
    "SHCB-1",
    "SHRGBW2",
)

# Bulbs that support white & color modes
DUAL_MODE_LIGHT_MODELS: Final = (
    "SHBLB-1",
    "SHCB-1",
)

# Refresh interval for REST sensors
REST_SENSORS_UPDATE_INTERVAL: Final = 60

# Refresh interval for RPC polling sensors
RPC_SENSORS_POLLING_INTERVAL: Final = 60

# Multiplier used to calculate the "update_interval" for sleeping devices.
SLEEP_PERIOD_MULTIPLIER: Final = 1.2
CONF_SLEEP_PERIOD: Final = "sleep_period"

# Multiplier used to calculate the "update_interval" for non-sleeping devices.
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
BATTERY_DEVICES_WITH_PERMANENT_CONNECTION: Final = ["SHMOS-01"]

# Button/Click events for Block & RPC devices
EVENT_SHELLY_CLICK: Final = "shelly.click"

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

SHBTN_MODELS: Final = ["SHBTN-1", "SHBTN-2"]

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

# Kelvin value for colorTemp
KELVIN_MAX_VALUE: Final = 6500
KELVIN_MIN_VALUE_WHITE: Final = 2700
KELVIN_MIN_VALUE_COLOR: Final = 3000

UPTIME_DEVIATION: Final = 5

# Time to wait before reloading entry upon device config change
ENTRY_RELOAD_COOLDOWN = 60

SHELLY_GAS_MODELS = ["SHGS-1"]

BLE_MIN_VERSION = AwesomeVersion("0.12.0-beta2")

CONF_BLE_SCANNER_MODE = "ble_scanner_mode"


class BLEScannerMode(StrEnum):
    """BLE scanner mode."""

    DISABLED = "disabled"
    ACTIVE = "active"
    PASSIVE = "passive"
