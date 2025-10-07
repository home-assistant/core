"""Common cover quirks for Tuya devices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .homeassistant import TuyaCoverDeviceClass


class CommonCoverType(StrEnum):
    """Common cover types."""

    CURTAIN = "curtain"


@dataclass(kw_only=True)
class TuyaCoverDefinition:
    """Definition for a cover entity."""

    key: str

    cover_type: CommonCoverType

    current_position_dp_code: str | None = None
    current_state_dp_code: str | None = None
    set_position_dp_code: str | None = None
    set_state_dp_code: str


# The following needs to be kept synchronised with Home Assistant


@dataclass(kw_only=True)
class CoverHADefinition:
    """Definition for a Tuya cover."""

    device_class: TuyaCoverDeviceClass | None = None
    translation_key: str
    translation_string: str


COMMON_COVER_DEFINITIONS: dict[CommonCoverType, CoverHADefinition] = {
    CommonCoverType.CURTAIN: CoverHADefinition(
        translation_key="curtain",
        translation_string="[%key:component::cover::entity_component::curtain::name%]",
        device_class=TuyaCoverDeviceClass.CURTAIN,
    )
}
