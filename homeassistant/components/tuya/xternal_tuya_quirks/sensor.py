"""Common cover quirks for Tuya devices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CommonSensorType(StrEnum):
    """Common sensor types."""

    TIME_TOTAL = "time_total"


@dataclass(kw_only=True)
class TuyaSensorDefinition:
    """Definition for a sensor entity."""

    key: str

    common_type: CommonSensorType

    dp_code: str
