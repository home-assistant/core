"""Constants for the SwitchBot Cloud integration."""

from datetime import timedelta
from enum import Enum
from typing import Final

DOMAIN: Final = "switchbot_cloud"
ENTRY_TITLE = "SwitchBot Cloud"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=600)

SENSOR_KIND_TEMPERATURE = "temperature"
SENSOR_KIND_HUMIDITY = "humidity"
SENSOR_KIND_BATTERY = "battery"

VACUUM_FAN_SPEED_QUIET = "quiet"
VACUUM_FAN_SPEED_STANDARD = "standard"
VACUUM_FAN_SPEED_STRONG = "strong"
VACUUM_FAN_SPEED_MAX = "max"


class SwitchBotCloudFanCommandS(Enum):
    """Command types currently supported by SwitchBot Cloud [Battery Circulator Fan] API."""

    SET_WIND_SPEED = "setWindSpeed"
    SET_WIND_MODE = "setWindMode"
    SET_NIGHT_LIGHT_MODE = "setNightLightMode"


class SwitchBotCloudFanMode(Enum):
    """Fan mode types currently supported by SwitchBot Cloud [Battery Circulator Fan] API."""

    DIRECT = "direct"
    NATURAL = "natural"
    SLEEP = "sleep"
    BABY = "baby"

    @classmethod
    def get_all_obj(cls) -> list:
        """Get all supported mode type as list."""
        return [cls.DIRECT, cls.NATURAL, cls.SLEEP, cls.BABY]
