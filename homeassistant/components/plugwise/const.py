"""Constants for Plugwise component."""

from datetime import timedelta
import logging
from typing import Final, Literal, get_args

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
LOWER_BOUND: Final = "lower_bound"
PW_TYPE: Final = "plugwise_type"
REBOOT: Final = "reboot"
SMILE: Final = "smile"
SMILE_OPEN_THERM: Final = "smile_open_therm"
SMILE_THERMO: Final = "smile_thermo"
STRETCH: Final = "stretch"
STRETCH_USERNAME: Final = "stretch"
UNKNOWN_SMILE: Final = "Unknown Smile"
UPPER_BOUND: Final = "upper_bound"

PLATFORMS: Final[list[str]] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]
ZEROCONF_MAP: Final[dict[str, str]] = {
    "smile": "Smile P1",
    "smile_thermo": "Smile Anna",
    "smile_open_therm": "Adam",
    "stretch": "Stretch",
}

type BinarySensorType = Literal["dhw_state"]

type NumberDataType = Literal[
    "asleep_preset_temperature",
    "away_preset_temperature",
    "boiler_temperature",
    "dhw_temperature",
    "home_preset_temperature",
    "no_frost_preset_temperature",
    "temperature_offset",
    "vacation_preset_temperature",
]

type PresetTemperatureType = Literal[
    "asleep_preset_temperature",
    "away_preset_temperature",
    "home_preset_temperature",
    "no_frost_preset_temperature",
    "vacation_preset_temperature",
]
PRESET_TEMPERATURE_KEYS: Final[tuple[PresetTemperatureType, ...]] = get_args(
    PresetTemperatureType.__value__
)

type PresetCoolingTemperatureType = Literal[
    "asleep_preset_cooling_temperature",
    "away_preset_cooling_temperature",
    "home_preset_cooling_temperature",
    "no_frost_preset_cooling_temperature",
    "vacation_preset_cooling_temperature",
]
PRESET_COOLING_TEMPERATURE_KEYS: Final[tuple[PresetCoolingTemperatureType, ...]] = (
    get_args(PresetCoolingTemperatureType.__value__)
)
type NumberType = NumberDataType | PresetCoolingTemperatureType

type SelectType = Literal[
    "dhw_mode",
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

type SetpointType = Literal["setpoint", "setpoint_high", "setpoint_low"]

type WaterHeaterType = Literal["dhw_temperature"]

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
DHW_MODE: Final = "dhw_mode"
SELECT_DHW_MODE: Final = "select_dhw_mode"
SELECT_GATEWAY_MODE: Final = "select_gateway_mode"
SELECT_REGULATION_MODE: Final = "select_regulation_mode"
SELECT_SCHEDULE: Final = "select_schedule"
SELECT_ZONE_PROFILE: Final = "select_zone_profile"

# Water_heater constants
DHW_TEMP: Final = "dhw_temperature"
