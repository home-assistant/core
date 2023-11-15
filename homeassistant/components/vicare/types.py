"""ViCare types."""
from enum import StrEnum


# Heating programs
class HeatingProgram(StrEnum):
    """ViCare preset heating programs.

    As listed in https://github.com/somm15/PyViCare/blob/8ba411483a865e074d1146fd1b8b7a8c4f4be122/PyViCare/PyViCareHeatingDevice.py#L564C27-L564C27
    """

    ACTIVE = "active"
    COMFORT = "comfort"
    ECO = "eco"
    EXTERNAL = "external"
    HOLIDAY = "holiday"
    NORMAL = "normal"
    REDUCED = "reduced"
    STANDBY = "standby"
    FIXED = "fixed"
    FORCED = "forcedLastFromSchedule"
