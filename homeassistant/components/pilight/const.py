"""Consts used by pilight."""

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import PilightData

DOMAIN = "pilight"

DATA_PILIGHT: HassKey[PilightData] = HassKey(DOMAIN)

EVENT = "pilight_received"
SERVICE_NAME = "send"

CONF_DIMLEVEL_MAX = "dimlevel_max"
CONF_DIMLEVEL_MIN = "dimlevel_min"
CONF_ECHO = "echo"
CONF_OFF = "off"
CONF_OFF_CODE = "off_code"
CONF_OFF_CODE_RECEIVE = "off_code_receive"
CONF_ON = "on"
CONF_ON_CODE = "on_code"
CONF_ON_CODE_RECEIVE = "on_code_receive"
CONF_SYSTEMCODE = "systemcode"
CONF_UNIT = "unit"
CONF_UNITCODE = "unitcode"
