"""Constants for the Eufy RoboVac integration."""

from enum import StrEnum

DOMAIN = "eufy_robovac"


class RoboVacCommand(StrEnum):
    """Canonical command names for model mappings."""

    START_PAUSE = "start_pause"
    DIRECTION = "direction"
    MODE = "mode"
    STATUS = "status"
    RETURN_HOME = "return_home"
    FAN_SPEED = "fan_speed"
    LOCATE = "locate"
    BATTERY = "battery"
    ERROR = "error"
