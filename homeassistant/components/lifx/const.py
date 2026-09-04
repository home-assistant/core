"""Const for LIFX."""

import logging
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .manager import LIFXManager

DOMAIN = "lifx"
DATA_LIFX_MANAGER: HassKey[LIFXManager] = HassKey(DOMAIN)

CONF_LABEL = "label"
CONF_SERIAL = "serial"

IDENTIFY = "identify"
RESTART = "restart"

ATTR_DURATION = "duration"
ATTR_INFRARED = "infrared"
ATTR_POWER = "power"
ATTR_RSSI = "rssi"
ATTR_ZONES = "zones"

ATTR_THEME = "theme"

ATTR_CHANGE = "change"
ATTR_CLOUD_SATURATION_MAX = "cloud_saturation_max"
ATTR_CLOUD_SATURATION_MIN = "cloud_saturation_min"
ATTR_CYCLES = "cycles"
ATTR_DIRECTION = "direction"
ATTR_PALETTE = "palette"
ATTR_PERIOD = "period"
ATTR_POWER_ON = "power_on"
ATTR_SATURATION_MAX = "saturation_max"
ATTR_SATURATION_MIN = "saturation_min"
ATTR_SKY_TYPE = "sky_type"
ATTR_SPEED = "speed"
ATTR_SPREAD = "spread"

SERVICE_EFFECT_COLORLOOP = "effect_colorloop"
SERVICE_EFFECT_FLAME = "effect_flame"
SERVICE_EFFECT_MORPH = "effect_morph"
SERVICE_EFFECT_MOVE = "effect_move"
SERVICE_EFFECT_PULSE = "effect_pulse"
SERVICE_EFFECT_SKY = "effect_sky"
SERVICE_EFFECT_STOP = "effect_stop"
SERVICE_PAINT_THEME = "paint_theme"

HEV_CYCLE_STATE = "hev_cycle_state"
LIFX_IDENTIFY_DELAY = 3.0
INFRARED_BRIGHTNESS = "infrared_brightness"
INFRARED_LEVELS = {
    "Disabled": 0.0,
    "25%": 0.25,
    "50%": 0.5,
    "100%": 1.0,
}

LOGGER = logging.getLogger(__package__)
