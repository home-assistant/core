"""Support for water heater devices."""

from enum import StrEnum
from typing import Final

from homeassistant.helpers.deprecation import EnumWithDeprecatedMembers

DOMAIN: Final = "water_heater"


class WaterHeaterCapabilityAttribute(StrEnum):
    """Capability attributes for water heater devices."""

    MIN_TEMP = "min_temp"
    MAX_TEMP = "max_temp"
    TARGET_TEMP_STEP = "target_temp_step"
    OPERATION_LIST = "operation_list"


class WaterHeaterStateAttribute(
    StrEnum,
    metaclass=EnumWithDeprecatedMembers,
    deprecated={
        "TEMPERATURE": ("ClimateEntityStateAttribute.TARGET_TEMPERATURE", "2027.3.0"),
    },
):
    """State attributes for water heater entities."""

    CURRENT_TEMPERATURE = "current_temperature"
    TARGET_TEMPERATURE = "temperature"
    TEMPERATURE = "temperature"  # Deprecated, replaced with TARGET_TEMPERATURE
    TARGET_TEMP_HIGH = "target_temp_high"
    TARGET_TEMP_LOW = "target_temp_low"
    OPERATION_MODE = "operation_mode"
    AWAY_MODE = "away_mode"


STATE_ECO = "eco"
STATE_ELECTRIC = "electric"
STATE_PERFORMANCE = "performance"
STATE_HIGH_DEMAND = "high_demand"
STATE_HEAT_PUMP = "heat_pump"
STATE_GAS = "gas"
