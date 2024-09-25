"""Constants for the EHEIM Digital integration."""

from logging import Logger, getLogger

from eheimdigital.types import LightMode

from homeassistant.components.light import EFFECT_OFF

LOGGER: Logger = getLogger(__package__)
DOMAIN = "eheimdigital"

DAYCL_MODE = "daycl_mode"

EFFECT_TO_LIGHT_MODE = {
    DAYCL_MODE: LightMode.DAYCL_MODE,
    EFFECT_OFF: LightMode.MAN_MODE,
}
