"""Constants for the Rointe Heaters integration."""

from enum import StrEnum
import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

DOMAIN = "rointe"
DEVICE_DOMAIN = "climate"
PLATFORMS: list[Platform] = [Platform.CLIMATE]
CONF_USERNAME = "rointe_username"
CONF_PASSWORD = "rointe_password"
CONF_INSTALLATION = "rointe_installation"

ROINTE_MANUFACTURER = "Rointe"

ROINTE_SUPPORTED_DEVICES = ["radiator", "towel", "therm", "radiatorb", "acs"]

RADIATOR_DEFAULT_TEMPERATURE = 20

PRESET_ROINTE_ICE = "ice"


class RointePreset(StrEnum):
    """Rointe radiators preset modes."""

    ECO = "eco"
    COMFORT = "comfort"
    ICE = "ice"
    NONE = "none"
    OFF = "off"


class RointeCommand(StrEnum):
    """Device commands."""

    SET_TEMP = "cmd_set_temp"
    SET_PRESET = "cmd_set_preset"
    SET_HVAC_MODE = "cmd_set_hvac_mode"


class RointeOperationMode(StrEnum):
    """Device operation mode."""

    AUTO = "auto"
    MANUAL = "manual"
