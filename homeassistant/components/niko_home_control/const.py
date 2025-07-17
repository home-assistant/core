"""Constants for niko_home_control integration."""

from enum import IntEnum
import logging

DOMAIN = "niko_home_control"
_LOGGER = logging.getLogger(__name__)

NIKO_HOME_CONTROL_THERMOSTAT_MODES_MAP = {
    "off": 3,
    "cool": 4,
    "auto": 5,
}


class NikoHomeControlThermostatModes(IntEnum):
    """Enum for Niko Home Control thermostat modes."""

    OFF = 3
    COOL = 4
    AUTO = 5
