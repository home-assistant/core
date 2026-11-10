"""Const for LIFX."""

from enum import StrEnum
import logging
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .manager import LIFXManager

DOMAIN = "lifx"
DATA_LIFX_MANAGER: HassKey[LIFXManager] = HassKey(DOMAIN)

CONF_GROUP = "group"
CONF_LABEL = "label"
CONF_MAC_ADDRESS = "mac_address"
CONF_NETWORK_NAME = "network_name"
CONF_SERIAL = "serial"
CONF_TITLE = "title"

IDENTIFY = "identify"
RESTART = "restart"

ATTR_RSSI = "rssi"


class LIFXService(StrEnum):
    """Store keys for LIFX services."""

    EFFECT_COLORLOOP = "effect_colorloop"
    EFFECT_COLORSWEEP = "effect_colorsweep"
    EFFECT_FLAME = "effect_flame"
    EFFECT_MORPH = "effect_morph"
    EFFECT_MOVE = "effect_move"
    EFFECT_PULSE = "effect_pulse"
    EFFECT_SKY = "effect_sky"
    EFFECT_STOP = "effect_stop"
    PAINT_THEME = "paint_theme"
    SET_HEV_CYCLE_STATE = "set_hev_cycle_state"
    SET_STATE = "set_state"


class LIFXServiceArgument(StrEnum):
    """Store keys for LIFX service arguments."""

    BRIGHTNESS = "brightness"
    BRIGHTNESS_PCT = "brightness_pct"
    CHANGE = "change"
    CLOUD_SATURATION_MAX = "cloud_saturation_max"
    CLOUD_SATURATION_MIN = "cloud_saturation_min"
    COLOR_NAME = "color_name"
    CYCLES = "cycles"
    DIRECTION = "direction"
    DURATION = "duration"
    INFRARED = "infrared"
    MODE = "mode"
    PALETTE = "palette"
    PERIOD = "period"
    POWER = "power"
    POWER_ON = "power_on"
    RGB_COLOR = "rgb_color"
    SATURATION_MAX = "saturation_max"
    SATURATION_MIN = "saturation_min"
    SKY_TYPE = "sky_type"
    SPEED = "speed"
    SPREAD = "spread"
    THEME = "theme"
    TRANSITION = "transition"
    ZONES = "zones"


HEV_CYCLE_STATE = "hev_cycle_state"
LIFX_IDENTIFY_DELAY = 3.0
# A bulb often misses one poll and answers the next, so it is only shown as
# unavailable once it has missed this many in a row
MAX_MISSED_POLLS = 3
INFRARED_BRIGHTNESS = "infrared_brightness"
INFRARED_LEVELS = {
    "Disabled": 0.0,
    "25%": 0.25,
    "50%": 0.5,
    "100%": 1.0,
}

LOGGER = logging.getLogger(__package__)
