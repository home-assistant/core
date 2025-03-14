"""Constants for the EHEIM Digital integration."""

from logging import Logger, getLogger

from eheimdigital.types import HeaterMode, LightMode

from homeassistant.components.climate import PRESET_NONE
from homeassistant.components.light import EFFECT_OFF

LOGGER: Logger = getLogger(__package__)
DOMAIN = "eheimdigital"

EFFECT_DAYCL_MODE = "daycl_mode"

EFFECT_TO_LIGHT_MODE = {
    EFFECT_DAYCL_MODE: LightMode.DAYCL_MODE,
    EFFECT_OFF: LightMode.MAN_MODE,
}

HEATER_BIO_MODE = "bio_mode"
HEATER_SMART_MODE = "smart_mode"

HEATER_PRESET_TO_HEATER_MODE = {
    HEATER_BIO_MODE: HeaterMode.BIO,
    HEATER_SMART_MODE: HeaterMode.SMART,
    PRESET_NONE: HeaterMode.MANUAL,
}
