"""Constants for rainbird."""

from enum import StrEnum

DOMAIN = "rainbird"
MANUFACTURER = "Rain Bird"
DEFAULT_TRIGGER_TIME_MINUTES = 6

CONF_SERIAL_NUMBER = "serial_number"
CONF_IMPORTED_NAMES = "imported_names"

ATTR_DURATION = "duration"

TIMEOUT_SECONDS = 20


class RainbirdService(StrEnum):
    """Store keys for Rain Bird services."""

    START_IRRIGATION = "start_irrigation"


class RainbirdServiceArgument(StrEnum):
    """Store keys for Rain Bird service arguments."""

    DURATION = "duration"
