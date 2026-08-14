"""Constants for the Dyson Infrared integration."""

from enum import StrEnum

DOMAIN = "dyson_infrared"
CONF_INFRARED_EMITTER_ENTITY_ID = "infrared_emitter_entity_id"
CONF_DEVICE_TYPE = "device_type"
CONF_COMMAND_STEP_DELAY = "command_step_delay"

DEFAULT_COMMAND_STEP_DELAY = 1


class DysonDeviceType(StrEnum):
    """Supported Dyson device types."""

    FAN = "fan"
    HEATER_COOLER = "heater_cooler"


class DysonTemperatureUnit(StrEnum):
    """Temperature unit the device itself is set to display."""

    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit"
