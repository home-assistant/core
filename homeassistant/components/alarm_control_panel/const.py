"""Provides the constants needed for component."""
from enum import IntFlag, StrEnum
from functools import partial
from typing import Final

from homeassistant.helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)

DOMAIN: Final = "alarm_control_panel"

ATTR_CHANGED_BY: Final = "changed_by"
ATTR_CODE_ARM_REQUIRED: Final = "code_arm_required"


class CodeFormat(StrEnum):
    """Code formats for the Alarm Control Panel."""

    TEXT = "text"
    NUMBER = "number"


# These constants are deprecated as of Home Assistant 2022.5, can be removed in 2025.1
# Please use the CodeFormat enum instead.
_DEPRECATED_FORMAT_TEXT: Final = DeprecatedConstantEnum(CodeFormat.TEXT, "2025.1")
_DEPRECATED_FORMAT_NUMBER: Final = DeprecatedConstantEnum(CodeFormat.NUMBER, "2025.1")


class AlarmControlPanelEntityFeature(IntFlag):
    """Supported features of the alarm control panel entity."""

    ARM_HOME = 1
    ARM_AWAY = 2
    ARM_NIGHT = 4
    TRIGGER = 8
    ARM_CUSTOM_BYPASS = 16
    ARM_VACATION = 32


# These constants are deprecated as of Home Assistant 2022.5
# Please use the AlarmControlPanelEntityFeature enum instead.
_DEPRECATED_SUPPORT_ALARM_ARM_HOME: Final = DeprecatedConstantEnum(
    AlarmControlPanelEntityFeature.ARM_HOME, "2025.1"
)
_DEPRECATED_SUPPORT_ALARM_ARM_AWAY: Final = DeprecatedConstantEnum(
    AlarmControlPanelEntityFeature.ARM_AWAY, "2025.1"
)
_DEPRECATED_SUPPORT_ALARM_ARM_NIGHT: Final = DeprecatedConstantEnum(
    AlarmControlPanelEntityFeature.ARM_NIGHT, "2025.1"
)
_DEPRECATED_SUPPORT_ALARM_TRIGGER: Final = DeprecatedConstantEnum(
    AlarmControlPanelEntityFeature.TRIGGER, "2025.1"
)
_DEPRECATED_SUPPORT_ALARM_ARM_CUSTOM_BYPASS: Final = DeprecatedConstantEnum(
    AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS, "2025.1"
)
_DEPRECATED_SUPPORT_ALARM_ARM_VACATION: Final = DeprecatedConstantEnum(
    AlarmControlPanelEntityFeature.ARM_VACATION, "2025.1"
)

CONDITION_TRIGGERED: Final = "is_triggered"
CONDITION_DISARMED: Final = "is_disarmed"
CONDITION_ARMED_HOME: Final = "is_armed_home"
CONDITION_ARMED_AWAY: Final = "is_armed_away"
CONDITION_ARMED_NIGHT: Final = "is_armed_night"
CONDITION_ARMED_VACATION: Final = "is_armed_vacation"
CONDITION_ARMED_CUSTOM_BYPASS: Final = "is_armed_custom_bypass"

# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
