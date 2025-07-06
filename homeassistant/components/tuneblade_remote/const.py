"""Constants for TuneBlade Remote integration."""

from enum import Enum, IntFlag

# Base component constants
NAME = "TuneBlade Remote"
DOMAIN = "tuneblade_remote"


class MediaPlayerState(str, Enum):
    """Media player states."""

    OFF = "off"
    IDLE = "idle"
    PLAYING = "playing"


class MediaPlayerEntityFeature(IntFlag):
    """Media player entity features."""

    TURN_ON = 1
    TURN_OFF = 2
    VOLUME_SET = 4
