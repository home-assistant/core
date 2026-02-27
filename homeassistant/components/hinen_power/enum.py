"""Hinen enums ."""

from enum import Enum


class DeviceStatus(Enum):
    """Hinen device status."""

    OFF = 0
    NORMAL = 1
    SLEEP = 2
    UNKNOWN = -1

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN


class DeviceAlertStatus(Enum):
    """Hinen device alert status."""

    NORMAL = 0
    ALARM = 1
    ERROR = 2
    UNKNOWN = -1

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN
