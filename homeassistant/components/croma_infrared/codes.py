"""IR codes for Croma Google TVs.

Standard NEC frames on a single address. Power is a toggle; the TV has no
discrete on or off codes.
"""

from enum import IntEnum

from infrared_protocols.commands import Command
from infrared_protocols.commands.nec import NECCommand

# Address 0x40 followed by its inverse, 0xBF.
CROMA_ADDRESS = 0xBF40


class CromaTVCode(IntEnum):
    """IR command codes for Croma TVs."""

    # Power
    POWER = 0x12

    # Volume
    VOLUME_UP = 0x1A
    VOLUME_DOWN = 0x1E
    MUTE = 0x10

    # Navigation
    UP = 0x19
    DOWN = 0x1D
    LEFT = 0x46
    RIGHT = 0x47
    OK = 0x0A
    BACK = 0x40
    EXIT = 0x44
    HOME = 0x51

    # System
    SETTINGS = 0x72
    APPS = 0x5E
    INPUT = 0x14
    INFO = 0x16
    PROFILE = 0x71
    ASSISTANT = 0x61
    SUBTITLES = 0x17
    CHANNEL_UP = 0x1B
    CHANNEL_DOWN = 0x1F

    # Apps
    YOUTUBE = 0x55
    NETFLIX = 0x58
    PRIME_VIDEO = 0x50
    LIVE_TV = 0x8C
    TV = 0x0B

    # Media
    PLAY = 0x57
    PAUSE = 0x48
    STOP = 0x54
    FAST_FORWARD = 0x4E
    REWIND = 0x4F

    def to_command(self) -> Command:
        """Build the NEC command for this code."""
        return NECCommand(address=CROMA_ADDRESS, command=self.value)
