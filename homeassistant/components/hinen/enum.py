"""Hinen enums ."""

from enum import Enum


class DeviceStatus(Enum):
    """Hinen device status."""

    OFF = 0
    NORMAL = 1
    SLEEP = 2

    @classmethod
    def get_display_name(cls, value: int) -> str:
        """Get display name."""
        mapping = {
            cls.NORMAL.value: "NORMAL",
            cls.OFF.value: "OFF",
            cls.SLEEP.value: "SLEEP",
        }

        return mapping.get(value, "UNKNOWN")


class DeviceAlertStatus(Enum):
    """Hinen device alert status."""

    NORMAL = 0
    ALARM = 1
    ERROR = 2

    @classmethod
    def get_display_name(cls, value: int) -> str:
        """Get display name."""
        mapping = {
            cls.NORMAL.value: "NORMAL",
            cls.ALARM.value: "ALARM",
            cls.ERROR.value: "ERROR",
        }

        return mapping.get(value, "UNKNOWN")
