"""Constants for the siren component."""

from enum import IntEnum
from typing import Final

DOMAIN: Final = "siren"

ATTR_TONE: Final = "tone"

ATTR_AVAILABLE_TONES: Final = "available_tones"
ATTR_DURATION: Final = "duration"
ATTR_VOLUME_LEVEL: Final = "volume_level"


class SirenEntityFeature(IntEnum):
    """Supported features of the siren entity."""

    TURN_ON = 1
    TURN_OFF = 2
    TONES = 4
    VOLUME_SET = 8
    DURATION = 16


# These constants are deprecated as of Home Assistant 2022.5
# Please use the SirenEntityFeature enum instead.
SUPPORT_TURN_ON: Final = 1
SUPPORT_TURN_OFF: Final = 2
SUPPORT_TONES: Final = 4
SUPPORT_VOLUME_SET: Final = 8
SUPPORT_DURATION: Final = 16
