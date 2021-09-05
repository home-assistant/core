"""Constants for the siren component."""

from typing import Final

DOMAIN: Final = "siren"

ATTR_TONE: Final = "tone"

ATTR_AVAILABLE_TONES: Final = "available_tones"
ATTR_DURATION: Final = "duration"
ATTR_VOLUME_LEVEL: Final = "volume_level"

SUPPORT_TURN_ON: Final = 1
SUPPORT_TURN_OFF: Final = 2
SUPPORT_TONES: Final = 4
SUPPORT_VOLUME_SET: Final = 8
SUPPORT_DURATION: Final = 16
