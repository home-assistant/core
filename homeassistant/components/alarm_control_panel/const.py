"""Provides the constants needed for component."""

from enum import IntFlag, StrEnum
from typing import Final

DOMAIN: Final = "alarm_control_panel"

ATTR_CHANGED_BY: Final = "changed_by"
ATTR_CODE_ARM_REQUIRED: Final = "code_arm_required"


class AlarmControlPanelState(StrEnum):
    """Alarm control panel entity states."""

    DISARMED = "disarmed"
    ARMED_HOME = "armed_home"
    ARMED_AWAY = "armed_away"
    ARMED_NIGHT = "armed_night"
    ARMED_VACATION = "armed_vacation"
    ARMED_CUSTOM_BYPASS = "armed_custom_bypass"
    PENDING = "pending"
    ARMING = "arming"
    DISARMING = "disarming"
    TRIGGERED = "triggered"


class CodeFormat(StrEnum):
    """Code formats for the Alarm Control Panel."""

    TEXT = "text"
    NUMBER = "number"


class AlarmControlPanelEntityFeature(IntFlag):
    """Supported features of the alarm control panel entity."""

    ARM_HOME = 1
    ARM_AWAY = 2
    ARM_NIGHT = 4
    TRIGGER = 8
    ARM_CUSTOM_BYPASS = 16
    ARM_VACATION = 32


CONDITION_TRIGGERED: Final = "is_triggered"
CONDITION_DISARMED: Final = "is_disarmed"
CONDITION_ARMED_HOME: Final = "is_armed_home"
CONDITION_ARMED_AWAY: Final = "is_armed_away"
CONDITION_ARMED_NIGHT: Final = "is_armed_night"
CONDITION_ARMED_VACATION: Final = "is_armed_vacation"
CONDITION_ARMED_CUSTOM_BYPASS: Final = "is_armed_custom_bypass"
