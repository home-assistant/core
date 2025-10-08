"""Common cover quirks for Tuya devices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CommonSelectType(StrEnum):
    """Common select types."""

    CONTROL_BACK_MODE = "control_back_mode"


@dataclass(kw_only=True)
class TuyaSelectDefinition:
    """Definition for a select entity."""

    key: str

    common_type: CommonSelectType

    dp_code: str
