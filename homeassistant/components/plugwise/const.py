"""Constants for Plugwise component."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "plugwise"

LOGGER = logging.getLogger(__package__)

API: Final = "api"
FLOW_SMILE: Final = "smile (Adam/Anna/P1)"
FLOW_STRETCH: Final = "stretch (Stretch)"
FLOW_TYPE: Final = "flow_type"
GATEWAY: Final = "gateway"
PW_TYPE: Final = "plugwise_type"
SMILE: Final = "smile"
STRETCH: Final = "stretch"
STRETCH_USERNAME: Final = "stretch"
UNIT_LUMEN: Final = "lm"

PLATFORMS_GATEWAY: Final[list[str]] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
]
ZEROCONF_MAP: Final[dict[str, str]] = {
    "smile": "P1",
    "smile_thermo": "Anna",
    "smile_open_therm": "Adam",
    "stretch": "Stretch",
}

# Default directives
DEFAULT_MAX_TEMP: Final = 30
DEFAULT_MIN_TEMP: Final = 4
DEFAULT_PORT: Final = 80
DEFAULT_SCAN_INTERVAL: Final[dict[str, timedelta]] = {
    "power": timedelta(seconds=10),
    "stretch": timedelta(seconds=60),
    "thermostat": timedelta(seconds=60),
}
DEFAULT_USERNAME: Final = "smile"

THERMOSTAT_CLASSES: Final[list[str]] = [
    "thermostat",
    "thermostatic_radiator_valve",
    "zone_thermometer",
    "zone_thermostat",
]
