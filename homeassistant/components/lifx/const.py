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
