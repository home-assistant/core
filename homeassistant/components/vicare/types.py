"""ViCare types."""
from enum import StrEnum


class ViCareProgram(StrEnum):
    """ViCare preset heating programs."""

    ACTIVE = "active"
    COMFORT = "comfort"
    ECO = "eco"
    EXTERNAL = "external"
    HOLIDAY = "holiday"
    NORMAL = "normal"
    REDUCED = "reduced"
    STANDBY = "standby"
