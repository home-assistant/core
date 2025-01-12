"""Constants for the siren component."""

from enum import IntFlag
from typing import Final

DOMAIN: Final = "siren"

ATTR_TONE: Final = "tone"

ATTR_AVAILABLE_TONES: Final = "available_tones"
ATTR_DURATION: Final = "duration"
ATTR_VOLUME_LEVEL: Final = "volume_level"


class SirenEntityFeature(IntFlag):
    """Supported features of the siren entity."""

    TURN_ON = 1
    TURN_OFF = 2
    TONES = 4
    VOLUME_SET = 8
    DURATION = 16
