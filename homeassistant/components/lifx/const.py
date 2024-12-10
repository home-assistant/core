"""Const for LIFX."""

import logging

DOMAIN = "lifx"

TARGET_ANY = "00:00:00:00:00:00"

DISCOVERY_INTERVAL = 10
# The number of seconds before we will no longer accept a response
# to a message and consider it invalid
MESSAGE_TIMEOUT = 18
# Disable the retries in the library since they are not spaced out
# enough to account for WiFi and UDP dropouts
MESSAGE_RETRIES = 1
OVERALL_TIMEOUT = 15
UNAVAILABLE_GRACE = 90

# The number of times to retry a request message
DEFAULT_ATTEMPTS = 5
# The maximum time to wait for a bulb to respond to an update
MAX_UPDATE_TIME = 90
# The number of tries to send each request message to a bulb during an update
MAX_ATTEMPTS_PER_UPDATE_REQUEST_MESSAGE = 5

CONF_LABEL = "label"
CONF_SERIAL = "serial"

IDENTIFY_WAVEFORM = {
    "transient": True,
    "color": [0, 0, 1, 3500],
    "skew_ratio": 0,
    "period": 1000,
    "cycles": 3,
    "waveform": 1,
    "set_hue": True,
    "set_saturation": True,
    "set_brightness": True,
    "set_kelvin": True,
}
IDENTIFY = "identify"
RESTART = "restart"

ATTR_DURATION = "duration"
ATTR_INDICATION = "indication"
ATTR_INFRARED = "infrared"
ATTR_POWER = "power"
ATTR_REMAINING = "remaining"
ATTR_RSSI = "rssi"
ATTR_ZONES = "zones"

ATTR_THEME = "theme"

HEV_CYCLE_STATE = "hev_cycle_state"
INFRARED_BRIGHTNESS = "infrared_brightness"
INFRARED_BRIGHTNESS_VALUES_MAP = {
    0: "Disabled",
    16383: "25%",
    32767: "50%",
    65535: "100%",
}
DATA_LIFX_MANAGER = "lifx_manager"

LIFX_CEILING_PRODUCT_IDS = {176, 177}

_LOGGER = logging.getLogger(__package__)

# _ATTR_COLOR_TEMP deprecated - to be removed in 2026.1
_ATTR_COLOR_TEMP = "color_temp"
