"""Constants for the Yardian integration."""

from enum import StrEnum

DOMAIN = "yardian"
MANUFACTURER = "Aeon Matrix"
PRODUCT_NAME = "Yardian Smart Sprinkler Controller"

DEFAULT_WATERING_DURATION = 6
SWITCH_ON_REFRESH_DELAY = 2
SWITCH_OFF_REFRESH_DELAY = 4
BUTTON_REFRESH_DELAY = 3


class YardianService(StrEnum):
    """Store keys for Yardian services."""

    START_IRRIGATION = "start_irrigation"


class YardianServiceArgument(StrEnum):
    """Store keys for Yardian service arguments."""

    DURATION = "duration"
