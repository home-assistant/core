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
REBOOT: Final = "reboot"
SMILE: Final = "smile"
SMILE_OPEN_THERM: Final = "smile_open_therm"
SMILE_THERMO: Final = "smile_thermo"
STRETCH: Final = "stretch"
STRETCH_USERNAME: Final = "stretch"
UNKNOWN_SMILE: Final = "Unknown Smile"

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
    "select_zone_profile",
]
type SelectOptionsType = Literal[
    "available_schedules",
    "dhw_modes",
    "gateway_modes",
    "regulation_modes",
    "zone_profiles",
]

# Default directives
DEFAULT_MAX_TEMP: Final = 30
DEFAULT_MIN_TEMP: Final = 4
DEFAULT_PORT: Final = 80
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=60)
DEFAULT_USERNAME: Final = "smile"
P1_UPDATE_INTERVAL = timedelta(seconds=10)

MASTER_THERMOSTATS: Final[list[str]] = [
    "thermostat",
    "thermostatic_radiator_valve",
    "zone_thermometer",
    "zone_thermostat",
]

# Select constants
SELECT_DHW_MODE: Final = "select_dhw_mode"
SELECT_GATEWAY_MODE: Final = "select_gateway_mode"
SELECT_REGULATION_MODE: Final = "select_regulation_mode"
SELECT_SCHEDULE: Final = "select_schedule"
SELECT_ZONE_PROFILE: Final = "select_zone_profile"
