"""Common climate quirks for Tuya devices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..const import DPCode


class CommonClimateType(StrEnum):
    """Common climate types."""

    SWITCH_ONLY_HEAT_COOL = "switch_only_heat_cool"


@dataclass(kw_only=True)
class TuyaClimateDefinition:
    """Definition for a climate entity."""

    key: str

    common_type: CommonClimateType

    current_temperature_dp_code: DPCode | None = None
    set_temperature_dp_code: DPCode | None = None
    switch_dp_code: DPCode | None = None
