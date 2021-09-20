"""Provides the constants needed for component."""

from typing import Final

SUPPORT_ALARM_ARM_HOME: Final = 1
SUPPORT_ALARM_ARM_AWAY: Final = 2
SUPPORT_ALARM_ARM_NIGHT: Final = 4
SUPPORT_ALARM_TRIGGER: Final = 8
SUPPORT_ALARM_ARM_CUSTOM_BYPASS: Final = 16

CONDITION_TRIGGERED: Final = "is_triggered"
CONDITION_DISARMED: Final = "is_disarmed"
CONDITION_ARMED_HOME: Final = "is_armed_home"
CONDITION_ARMED_AWAY: Final = "is_armed_away"
CONDITION_ARMED_NIGHT: Final = "is_armed_night"
CONDITION_ARMED_CUSTOM_BYPASS: Final = "is_armed_custom_bypass"
