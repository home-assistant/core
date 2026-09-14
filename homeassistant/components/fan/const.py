"""Constants for the fan component."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import FanEntity


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


DOMAIN: Final = "fan"

DATA_COMPONENT: HassKey[EntityComponent[FanEntity]] = HassKey(DOMAIN)
