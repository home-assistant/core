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

AFTER_COMMAND_REFRESH = 5
COVER_ENTITY_AFTER_COMMAND_REFRESH = 10


class AirPurifierMode(Enum):
    """Air Purifier Modes."""

    NORMAL = 1
    AUTO = 2
    SLEEP = 3
    PET = 4

    @classmethod
    def get_modes(cls) -> list[str]:
        """Return a list of available air purifier modes as lowercase strings."""
        return [mode.name.lower() for mode in cls]
