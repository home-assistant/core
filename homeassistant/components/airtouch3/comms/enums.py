"""Defines enumerations for AirTouch AC modes and zone statuses."""

from enum import Enum


class AcMode(Enum):
    """Enumeration of possible AirTouch AC operating modes."""

    AUTO = 0
    HEAT = 1
    DRY = 2
    FAN = 3
    COOL = 4


class ZoneStatus(Enum):
    """Enumeration of possible zone power statuses."""

    ZONE_OFF = 0
    ZONE_ON = 1
