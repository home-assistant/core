"""IR protocol definitions for the Infrared integration."""

import abc
from dataclasses import dataclass
from enum import StrEnum
from typing import override


class InfraredProtocol(StrEnum):
    """IR protocol type identifiers."""

    NEC = "nec"
    SAMSUNG = "samsung"


@dataclass(frozen=True, slots=True)
class Timing:
    """High/low signal timing."""

    high_us: int
    low_us: int


class InfraredCommand(abc.ABC):
    """Base class for IR commands."""

    protocol: InfraredProtocol
    repeat_count: int

    def __init__(self, *, repeat_count: int = 0) -> None:
        """Initialize the IR command."""
        self.repeat_count = repeat_count

    @abc.abstractmethod
    def get_raw_timings(self) -> list[Timing]:
        """Get raw timings for the command."""


class NECInfraredCommand(InfraredCommand):
    """NEC IR command."""

    protocol = InfraredProtocol.NEC
    address: int
    command: int

    def __init__(self, *, address: int, command: int, repeat_count: int = 0) -> None:
        """Initialize the NEC IR command."""
        super().__init__(repeat_count=repeat_count)
        self.address = address
        self.command = command

    @override
    def get_raw_timings(self) -> list[Timing]:
        """Get raw timings for the NEC command.

        NEC protocol timing (in microseconds):
        - Leader pulse: 9000µs high, 4500µs low
        - Logical '0': 562µs high, 562µs low
        - Logical '1': 562µs high, 1687µs low
        - End pulse: 562µs high
        - Repeat code: 9000µs high, 2250µs low, 562µs end pulse
        - Frame gap: ~96ms between end pulse and next frame (total frame ~108ms)

        Data format (32 bits, LSB first):
        - Standard NEC: address (8-bit) + ~address (8-bit) + command (8-bit) + ~command (8-bit)
        - Extended NEC: address_low (8-bit) + address_high (8-bit) + command (8-bit) + ~command (8-bit)
        """
        # NEC timing constants (microseconds)
        leader_high = 9000
        leader_low = 4500
        bit_high = 562
        zero_low = 562
        one_low = 1687
        repeat_low = 2250
        frame_gap = 96000  # Gap to make total frame ~108ms

        timings: list[Timing] = [Timing(high_us=leader_high, low_us=leader_low)]

        # Determine if standard (8-bit) or extended (16-bit) address
        if self.address <= 0xFF:
            # Standard NEC: address + inverted address
            address_low = self.address & 0xFF
            address_high = (~self.address) & 0xFF
        else:
            # Extended NEC: 16-bit address (no inversion)
            address_low = self.address & 0xFF
            address_high = (self.address >> 8) & 0xFF

        command_byte = self.command & 0xFF
        command_inverted = (~self.command) & 0xFF

        # Build 32-bit command data (LSB first in transmission)
        data = (
            address_low
            | (address_high << 8)
            | (command_byte << 16)
            | (command_inverted << 24)
        )

        for _ in range(32):
            bit = data & 1
            if bit:
                timings.append(Timing(high_us=bit_high, low_us=one_low))
            else:
                timings.append(Timing(high_us=bit_high, low_us=zero_low))
            data >>= 1

        # End pulse
        timings.append(Timing(high_us=bit_high, low_us=0))

        # Add repeat codes if requested
        for _ in range(self.repeat_count):
            # Replace the last timing's low_us with the frame gap
            last_timing = timings[-1]
            timings[-1] = Timing(high_us=last_timing.high_us, low_us=frame_gap)

            # Repeat code: leader burst + shorter space + end pulse
            timings.append(Timing(high_us=leader_high, low_us=repeat_low))
            timings.append(Timing(high_us=bit_high, low_us=0))

        return timings
