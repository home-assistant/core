"""Common cover quirks for Tuya devices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..const import DPCode


class CommonCoverType(StrEnum):
    """Common cover types."""

    CURTAIN = "curtain"


@dataclass(kw_only=True)
class TuyaCoverDefinition:
    """Definition for a cover entity."""

    key: str

    common_type: CommonCoverType

    current_position_dp_code: DPCode | None = None
    current_state_dp_code: DPCode | None = None
    set_position_dp_code: DPCode | None = None
    set_state_dp_code: DPCode
