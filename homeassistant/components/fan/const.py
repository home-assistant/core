"""Constants for the fan component."""

from enum import StrEnum


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
