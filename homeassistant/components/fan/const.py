"""Constants for the fan component."""

from enum import IntFlag, StrEnum
from typing import Final

DOMAIN: Final = "fan"


class FanEntityCapabilityAttribute(StrEnum):
    """Capability attributes for fan entities."""

    PRESET_MODES = "preset_modes"


class FanEntityStateAttribute(StrEnum):
    """State attributes for fan entities."""

    DIRECTION = "direction"
    OSCILLATING = "oscillating"
    PERCENTAGE = "percentage"
    PERCENTAGE_STEP = "percentage_step"
    PRESET_MODE = "preset_mode"


class FanEntityFeature(IntFlag):
    """Supported features of the fan entity."""

    SET_SPEED = 1
    OSCILLATE = 2
    DIRECTION = 4
    PRESET_MODE = 8
    TURN_OFF = 16
    TURN_ON = 32
