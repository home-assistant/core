"""Constants for niko_home_control integration."""

from enum import IntEnum
import logging

from homeassistant.components.climate import HVACMode

DOMAIN = "niko_home_control"
_LOGGER = logging.getLogger(__name__)

NIKO_HOME_CONTROL_THERMOSTAT_MODES_MAP = {
    HVACMode.OFF: 3,
    HVACMode.COOL: 4,
    HVACMode.AUTO: 5,
}


class NikoHomeControlThermostatModes(IntEnum):
    """Enum for Niko Home Control thermostat modes."""

    OFF = 3
    COOL = 4
    AUTO = 5
