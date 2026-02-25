"""Constants for the Eufy RoboVac integration."""

from enum import StrEnum

from homeassistant.const import Platform

DOMAIN = "eufy_robovac"
PLATFORMS: list[Platform] = [Platform.VACUUM]

CONF_LOCAL_KEY = "local_key"


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
