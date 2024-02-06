"""Define constants for the Sun WEG component."""
from enum import Enum

from homeassistant.const import Platform


class DeviceType(Enum):
    """Device Type Enum."""

    TOTAL = 1
    INVERTER = 2
    PHASE = 3
    STRING = 4


CONF_PLANT_ID = "plant_id"

DEFAULT_PLANT_ID = 0

DEFAULT_NAME = "Sun WEG"

DOMAIN = "sunweg"

PLATFORMS = [Platform.SENSOR]
