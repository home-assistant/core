"""IR codes for NAD audio equipment.

All NAD components share one NEC address; each device only responds to its own
codes. The amplifier codes come from NAD's "IR Commands by Model" tables for the
T 175, T 187, T 765, T 775, T 777, T 785 and T 787, and were confirmed with a NAD
AVR 4 remote. The CD player and cassette deck codes come from NAD remotes in the IRDB.
They are standard NEC frames on IR channel 0; NAD's other IR channels use a
non-NEC variant of the frame.
"""

from enum import IntEnum

from infrared_protocols.commands import Command
from infrared_protocols.commands.nec import NECCommand

# NAD documents the customer code as 877C: first byte 0x87, second byte 0x7C.
NAD_ADDRESS = 0x7C87


class NADAmplifierCode(IntEnum):
    """IR command codes for NAD amplifiers and receivers."""

    # Power
    ON = 0x25
    OFF = 0xC8

    # Volume
    VOLUME_UP = 0x88
    VOLUME_DOWN = 0x8C
    MUTE = 0x94

    # Sources
    INPUT_1 = 0xC2
    INPUT_2 = 0xC0
    INPUT_3 = 0xC1
    INPUT_4 = 0x30
    INPUT_5 = 0x31
    INPUT_6 = 0x1E
    INPUT_7 = 0x60
    FRONT = 0x85
    MP = 0x89
    # Selects the tuner; when already selected, steps through AM, FM and DAB.
    TUNER = 0xDD

    # Listening modes
    PLIIX_MOVIE = 0x6B
    PLIIX_MUSIC = 0x6A
    DOLBY_SURROUND_EX = 0x69
    NEO6_CINEMA = 0x6C
    NEO6_MUSIC = 0x6D
    MATRIX_7_1 = 0x6E
    EARS = 0x6F
    ENHANCED_STEREO_1 = 0x70
    STEREO_DOWNMIX = 0x65
    DIRECT = 0x64
    BYPASS = 0xDB

    def to_command(self) -> Command:
        """Build the NEC command for this code."""
        return NECCommand(address=NAD_ADDRESS, command=self.value)


class NADCDCode(IntEnum):
    """IR command codes for NAD CD players."""

    PLAY = 0x01
    STOP = 0x02
    SKIP_BACK = 0x05
    SKIP_FORWARD = 0x06
    PAUSE = 0x4A

    def to_command(self) -> Command:
        """Build the NEC command for this code."""
        return NECCommand(address=NAD_ADDRESS, command=self.value)


class NADCassetteCode(IntEnum):
    """IR command codes for NAD cassette decks.

    Single-cassette decks respond to the deck B codes.
    """

    DECK_B_PLAY = 0x9C
    DECK_B_PAUSE = 0x99
    DECK_B_STOP = 0x9F

    def to_command(self) -> Command:
        """Build the NEC command for this code."""
        return NECCommand(address=NAD_ADDRESS, command=self.value)
