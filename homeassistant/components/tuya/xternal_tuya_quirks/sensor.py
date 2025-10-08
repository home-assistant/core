"""Common sensor quirks for Tuya devices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from tuya_sharing import CustomerDevice

from ..const import DPCode
from ..models import EnumTypeData, IntegerTypeData


class CommonSensorType(StrEnum):
    """Common sensor types."""

    TEMPERATURE = "temperature"
    TIME_TOTAL = "time_total"


@dataclass(kw_only=True)
class TuyaSensorDefinition:
    """Definition for a sensor entity."""

    key: DPCode

    common_type: CommonSensorType

    state_conversion: (
        Callable[[CustomerDevice, EnumTypeData | IntegerTypeData | None, Any], Any]
        | None
    ) = None
