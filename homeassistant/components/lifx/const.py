"""Const for LIFX."""

import logging

DOMAIN = "lifx"

TARGET_ANY = "00:00:00:00:00:00"

DISCOVERY_INTERVAL = 10
MESSAGE_TIMEOUT = 1.65
MESSAGE_RETRIES = 5
OVERALL_TIMEOUT = 9
UNAVAILABLE_GRACE = 90

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

_LOGGER = logging.getLogger(__package__)
