"""Constants for the Shelly integration."""
from __future__ import annotations

from typing import Final

COAP: Final = "coap"
DATA_CONFIG_ENTRY: Final = "config_entry"
DEVICE: Final = "device"
DOMAIN: Final = "shelly"
REST: Final = "rest"

CONF_COAP_PORT: Final = "coap_port"
DEFAULT_COAP_PORT: Final = 5683

# Used in "_async_update_data" as timeout for polling data from devices.
POLLING_TIMEOUT_SEC: Final = 18

# Refresh interval for REST sensors
REST_SENSORS_UPDATE_INTERVAL: Final = 60

# Timeout used for aioshelly calls
AIOSHELLY_DEVICE_TIMEOUT_SEC: Final = 10

# Multiplier used to calculate the "update_interval" for sleeping devices.
SLEEP_PERIOD_MULTIPLIER: Final = 1.2

# Multiplier used to calculate the "update_interval" for non-sleeping devices.
UPDATE_PERIOD_MULTIPLIER: Final = 2.2

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

EVENT_SHELLY_CLICK: Final = "shelly.click"

ATTR_CLICK_TYPE: Final = "click_type"
ATTR_CHANNEL: Final = "channel"
ATTR_DEVICE: Final = "device"
CONF_SUBTYPE: Final = "subtype"

BASIC_INPUTS_EVENTS_TYPES: Final = {"single", "long"}

SHBTN_INPUTS_EVENTS_TYPES: Final = {"single", "double", "triple", "long"}

SUPPORTED_INPUTS_EVENTS_TYPES: Final = {
    "single",
    "double",
    "triple",
    "long",
    "single_long",
    "long_single",
}

SHIX3_1_INPUTS_EVENTS_TYPES = SUPPORTED_INPUTS_EVENTS_TYPES

INPUTS_EVENTS_SUBTYPES: Final = {"button": 1, "button1": 1, "button2": 2, "button3": 3}

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

# Kelvin value for colorTemp
KELVIN_MAX_VALUE: Final = 6500
KELVIN_MIN_VALUE_WHITE: Final = 2700
KELVIN_MIN_VALUE_COLOR: Final = 3000

UPTIME_DEVIATION: Final = 5

LAST_RESET_UPTIME: Final = "uptime"
LAST_RESET_NEVER: Final = "never"
