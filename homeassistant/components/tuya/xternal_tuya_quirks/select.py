"""Common cover quirks for Tuya devices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .homeassistant import TuyaEntityCategory


class CommonSelectType(StrEnum):
    """Common select types."""

    CONTROL_BACK_MODE = "control_back_mode"


@dataclass(kw_only=True)
class TuyaSelectDefinition:
    """Definition for a select entity."""

    key: str

    select_type: CommonSelectType

    dp_code: str


# The following needs to be kept synchronised with Home Assistant


@dataclass(kw_only=True)
class SelectHADefinition:
    """Definition for a Tuya select."""

    entity_category: TuyaEntityCategory | None = None
    state_translations: dict[str, str] | None = None
    translation_key: str
    translation_string: str


COMMON_SELECT_DEFINITIONS: dict[CommonSelectType, SelectHADefinition] = {
    CommonSelectType.CONTROL_BACK_MODE: SelectHADefinition(
        entity_category=TuyaEntityCategory.CONFIG,
        state_translations={"forward": "Forward", "back": "Back"},
        translation_key="curtain_motor_mode",
        translation_string="Motor mode",
    )
}
