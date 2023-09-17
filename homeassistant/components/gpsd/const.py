"""Constants for the GPSD integration."""

from typing import Final

DOMAIN: Final = "gpsd"

ATTR_CLIMB: Final = "climb"
ATTR_SPEED: Final = "speed"

DEFAULT_HOST: Final = "localhost"
DEFAULT_NAME: Final = "GPS"
DEFAULT_PORT: Final = 2947
