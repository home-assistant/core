"""Constants for the siren component."""

from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import SirenEntity


DOMAIN: Final = "siren"
DATA_COMPONENT: HassKey[EntityComponent[SirenEntity]] = HassKey(DOMAIN)

ATTR_TONE: Final = "tone"

ATTR_AVAILABLE_TONES: Final = "available_tones"
ATTR_DURATION: Final = "duration"
ATTR_VOLUME_LEVEL: Final = "volume_level"


class SirenEntityCapabilityAttribute(StrEnum):
    """Capability attributes for siren entities."""

    AVAILABLE_TONES = "available_tones"


class SirenEntityFeature(IntFlag):
    """Supported features of the siren entity."""

    TURN_ON = 1
    TURN_OFF = 2
    TONES = 4
    VOLUME_SET = 8
    DURATION = 16
