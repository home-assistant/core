"""Common switch quirks for Tuya devices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..const import DPCode


class CommonSwitchType(StrEnum):
    """Common switch types."""

    CHILD_LOCK = "child_lock"


@dataclass(kw_only=True)
class TuyaSwitchDefinition:
    """Definition for a switch entity."""

    key: DPCode

    common_type: CommonSwitchType
