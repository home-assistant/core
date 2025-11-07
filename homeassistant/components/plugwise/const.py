"""Constants for Plugwise component."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final, Literal

from homeassistant.const import Platform

DOMAIN: Final = "plugwise"

LOGGER = logging.getLogger(__package__)

ANNA_WITH_ADAM: Final = "anna_with_adam"
API: Final = "api"
AVAILABLE: Final = "available"
DEV_CLASS: Final = "dev_class"
FLOW_SMILE: Final = "smile (Adam/Anna/P1)"
FLOW_STRETCH: Final = "stretch (Stretch)"
FLOW_TYPE: Final = "flow_type"
GATEWAY: Final = "gateway"
LOCATION: Final = "location"
PW_TYPE: Final = "plugwise_type"
PLUGWISE: Final = "Plugwise"
REBOOT: Final = "reboot"
SMILE: Final = "smile"
SMILE_OPEN_THERM: Final = "smile_open_therm"
SMILE_THERMO: Final = "smile_thermo"
STRETCH: Final = "stretch"
STRETCH_USERNAME: Final = "stretch"
TITLE_PLACEHOLDERS: Final = "title_placeholders"
UNKNOWN_SMILE : Final = "Unknown Smile"

PLATFORMS: Final[list[str]] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]
ZEROCONF_MAP: Final[dict[str, str]] = {
    "smile": "Smile P1",
    "smile_thermo": "Smile Anna",
    "smile_open_therm": "Adam",
    "stretch": "Stretch",
}

type NumberType = Literal[
    "maximum_boiler_temperature",
    "max_dhw_temperature",
    "temperature_offset",
]

type SelectType = Literal[
    "select_dhw_mode",
    "select_gateway_mode",
    "select_regulation_mode",
    "select_schedule",
]
type SelectOptionsType = Literal[
    "dhw_modes",
    "gateway_modes",
    "regulation_modes",
    "available_schedules",
]

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

MASTER_THERMOSTATS: Final[list[str]] = [
    "thermostat",
    "thermostatic_radiator_valve",
    "zone_thermometer",
    "zone_thermostat",
]
