"""Constants for the fan component."""

from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import FanEntity

DOMAIN: Final = "fan"
DATA_COMPONENT: HassKey[EntityComponent[FanEntity]] = HassKey(DOMAIN)

SERVICE_INCREASE_SPEED = "increase_speed"
SERVICE_DECREASE_SPEED = "decrease_speed"
SERVICE_OSCILLATE = "oscillate"
SERVICE_SET_DIRECTION = "set_direction"
SERVICE_SET_PERCENTAGE = "set_percentage"
SERVICE_SET_PRESET_MODE = "set_preset_mode"

DIRECTION_FORWARD = "forward"
DIRECTION_REVERSE = "reverse"

ATTR_PERCENTAGE = "percentage"
ATTR_PERCENTAGE_STEP = "percentage_step"
ATTR_OSCILLATING = "oscillating"
ATTR_DIRECTION = "direction"
ATTR_PRESET_MODE = "preset_mode"
ATTR_PRESET_MODES = "preset_modes"


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
