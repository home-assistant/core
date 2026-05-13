"""Constants for the place integration."""

from enum import IntEnum

DOMAIN = "gentex_place"


class AlarmStatus(IntEnum):
    """Alarm status values."""

    IDLE = 0
    TEST = 1
    PRE_ALARM = 2
    ALARM = 3
    CRITICAL_ALARM = 4
    HUSHED = 5
    NOT_PRESENT = 6
