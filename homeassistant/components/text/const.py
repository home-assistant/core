"""Provides the constants needed for the component."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from .entity import TextEntity

DOMAIN: Final = "text"
DATA_COMPONENT: HassKey[EntityComponent[TextEntity]] = HassKey(DOMAIN)


class TextEntityCapabilityAttribute(StrEnum):
    """Capability attributes for text entities."""

    MODE = "mode"
    MIN = "min"
    MAX = "max"
    PATTERN = "pattern"


ATTR_MAX = "max"
ATTR_MIN = "min"
ATTR_PATTERN = "pattern"
ATTR_VALUE = "value"

SERVICE_SET_VALUE = "set_value"


class TextMode(StrEnum):
    """Modes for text entities."""

    PASSWORD = "password"
    TEXT = "text"
