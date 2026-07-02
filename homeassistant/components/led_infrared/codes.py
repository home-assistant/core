"""Todo: Move to infrared_protocols."""

from enum import IntEnum

from infrared_protocols.commands import Command
from infrared_protocols.commands.nec import NECCommand


class Generic13KeyCode(IntEnum):
    """Generic 13-key LED remote control IR command codes."""

    ON = 0x45
    TIMER = 0x46
    OFF = 0x47
    MODE_1 = 0x44
    MODE_2 = 0x43
    MODE_3 = 0x07
    MODE_4 = 0x09
    MODE_5 = 0x16
    MODE_6 = 0x0D
    MODE_7 = 0x0C
    MODE_8 = 0x5E
    BRIGHTNESS_UP = 0x5A
    BRIGHTNESS_DOWN = 0x08

    def to_command(self, repeat_count: int = 0) -> Command:
        """Build a NEC command."""
        return NECCommand(
            address=0xFF00,
            command=self.value,
            repeat_count=repeat_count,
        )
