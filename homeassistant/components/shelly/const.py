"""Constants for the Shelly integration."""

COAP = "coap"
DATA_CONFIG_ENTRY = "config_entry"
DEVICE = "device"
DOMAIN = "shelly"
REST = "rest"

CONF_COAP_PORT = "coap_port"
DEFAULT_COAP_PORT = 5683

# Used in "_async_update_data" as timeout for polling data from devices.
POLLING_TIMEOUT_SEC = 18

# Refresh interval for REST sensors
REST_SENSORS_UPDATE_INTERVAL = 60

# Timeout used for aioshelly calls
AIOSHELLY_DEVICE_TIMEOUT_SEC = 10

# Multiplier used to calculate the "update_interval" for sleeping devices.
SLEEP_PERIOD_MULTIPLIER = 1.2

# Multiplier used to calculate the "update_interval" for non-sleeping devices.
UPDATE_PERIOD_MULTIPLIER = 2.2

# Shelly Air - Maximum work hours before lamp replacement
SHAIR_MAX_WORK_HOURS = 9000

# Map Shelly input events
INPUTS_EVENTS_DICT = {
    "S": "single",
    "SS": "double",
    "SSS": "triple",
    "L": "long",
    "SL": "single_long",
    "LS": "long_single",
}

# List of battery devices that maintain a permanent WiFi connection
BATTERY_DEVICES_WITH_PERMANENT_CONNECTION = ["SHMOS-01"]

EVENT_SHELLY_CLICK = "shelly.click"

ATTR_CLICK_TYPE = "click_type"
ATTR_CHANNEL = "channel"
ATTR_DEVICE = "device"
CONF_SUBTYPE = "subtype"

BASIC_INPUTS_EVENTS_TYPES = {
    "single",
    "long",
}

SHBTN_INPUTS_EVENTS_TYPES = {
    "single",
    "double",
    "triple",
    "long",
}

SUPPORTED_INPUTS_EVENTS_TYPES = SHIX3_1_INPUTS_EVENTS_TYPES = {
    "single",
    "double",
    "triple",
    "long",
    "single_long",
    "long_single",
}

INPUTS_EVENTS_SUBTYPES = {
    "button": 1,
    "button1": 1,
    "button2": 2,
    "button3": 3,
}

SHBTN_MODELS = ["SHBTN-1", "SHBTN-2"]

STANDARD_RGB_EFFECTS = {
    0: "Off",
    1: "Meteor Shower",
    2: "Gradual Change",
    3: "Flash",
}

SHBLB_1_RGB_EFFECTS = {
    0: "Off",
    1: "Meteor Shower",
    2: "Gradual Change",
    3: "Flash",
    4: "Breath",
    5: "On/Off Gradual",
    6: "Red/Green Change",
}

# Kelvin value for colorTemp
KELVIN_MAX_VALUE = 6500
KELVIN_MIN_VALUE_WHITE = 2700
KELVIN_MIN_VALUE_COLOR = 3000

UPTIME_DEVIATION = 5
