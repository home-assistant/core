"""Common sensor quirks for Tuya devices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..const import DPCode


class CommonSensorType(StrEnum):
    """Common sensor types."""

    TIME_TOTAL = "time_total"


@dataclass(kw_only=True)
class TuyaSensorDefinition:
    """Definition for a sensor entity."""

    key: DPCode

    common_type: CommonSensorType
