"""Provides the constants needed for component."""
from enum import IntEnum
from typing import Final

from homeassistant.backports.enum import StrEnum

DOMAIN: Final = "alarm_control_panel"

ATTR_CHANGED_BY: Final = "changed_by"
ATTR_CODE_ARM_REQUIRED: Final = "code_arm_required"


class CodeFormat(StrEnum):
    """Code formats for the Alarm Control Panel."""

    TEXT = "text"
    NUMBER = "number"


# These constants are deprecated as of Home Assistant 2022.5
# Please use the CodeFormat enum instead.
FORMAT_TEXT: Final = "text"
FORMAT_NUMBER: Final = "number"


class AlarmControlPanelEntityFeature(IntEnum):
    """Supported features of the alarm control panel entity."""

    ARM_HOME = 1
    ARM_AWAY = 2
    ARM_NIGHT = 4
    TRIGGER = 8
    ARM_CUSTOM_BYPASS = 16
    ARM_VACATION = 32


# These constants are deprecated as of Home Assistant 2022.5
# Please use the AlarmControlPanelEntityFeature enum instead.
SUPPORT_ALARM_ARM_HOME: Final = 1
SUPPORT_ALARM_ARM_AWAY: Final = 2
SUPPORT_ALARM_ARM_NIGHT: Final = 4
SUPPORT_ALARM_TRIGGER: Final = 8
SUPPORT_ALARM_ARM_CUSTOM_BYPASS: Final = 16
SUPPORT_ALARM_ARM_VACATION: Final = 32

CONDITION_TRIGGERED: Final = "is_triggered"
CONDITION_DISARMED: Final = "is_disarmed"
CONDITION_ARMED_HOME: Final = "is_armed_home"
CONDITION_ARMED_AWAY: Final = "is_armed_away"
CONDITION_ARMED_NIGHT: Final = "is_armed_night"
CONDITION_ARMED_VACATION: Final = "is_armed_vacation"
CONDITION_ARMED_CUSTOM_BYPASS: Final = "is_armed_custom_bypass"
