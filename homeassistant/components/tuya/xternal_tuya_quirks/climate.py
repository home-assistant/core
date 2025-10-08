"""Common climate quirks for Tuya devices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..models import StateConversionFunction


class CommonClimateType(StrEnum):
    """Common climate types."""

    SWITCH_ONLY_HEAT_COOL = "switch_only_heat_cool"


@dataclass(kw_only=True)
class TuyaClimateDefinition:
    """Definition for a climate entity."""

    key: str

    common_type: CommonClimateType

    current_temperature_state_conversion: StateConversionFunction | None = None
    target_temperature_state_conversion: StateConversionFunction | None = None
    target_temperature_command_conversion: StateConversionFunction | None = None
