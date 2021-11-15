"""Constants for the Shelly integration."""
from __future__ import annotations

import re
from typing import Final

BLOCK: Final = "block"
DATA_CONFIG_ENTRY: Final = "config_entry"
DEVICE: Final = "device"
DOMAIN: Final = "shelly"
REST: Final = "rest"
RPC: Final = "rpc"

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

# Used in "_async_update_data" as timeout for polling data from devices.
POLLING_TIMEOUT_SEC: Final = 18

# Refresh interval for REST sensors
REST_SENSORS_UPDATE_INTERVAL: Final = 60

# Timeout used for aioshelly calls
AIOSHELLY_DEVICE_TIMEOUT_SEC: Final = 10

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

BASIC_INPUTS_EVENTS_TYPES: Final = {"single", "long"}

SHBTN_INPUTS_EVENTS_TYPES: Final = {"single", "double", "triple", "long"}

RPC_INPUTS_EVENTS_TYPES: Final = {
    "btn_down",
    "btn_up",
    "single_push",
    "double_push",
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
    "step": 1,
}

# Kelvin value for colorTemp
KELVIN_MAX_VALUE: Final = 6500
KELVIN_MIN_VALUE_WHITE: Final = 2700
KELVIN_MIN_VALUE_COLOR: Final = 3000

UPTIME_DEVIATION: Final = 5

# Max RPC switch/input key instances
MAX_RPC_KEY_INSTANCES = 4

# Time to wait before reloading entry upon device config change
ENTRY_RELOAD_COOLDOWN = 60
