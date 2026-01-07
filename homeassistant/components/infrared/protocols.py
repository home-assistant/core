"""IR protocol definitions for the Infrared integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class InfraredProtocolType(StrEnum):
    """IR protocol type identifiers."""

    PULSE_WIDTH = "pulse_width"
    NEC = "nec"
    SAMSUNG = "samsung"


PULSE_WIDTH_COMPAT_PROTOCOLS = {InfraredProtocolType.NEC, InfraredProtocolType.SAMSUNG}


@dataclass(frozen=True, slots=True)
class IRTiming:
    """Timing for a signal component."""

    high_us: int
    low_us: int


class InfraredProtocol:
    """Base class for IR protocol definitions."""

    type: InfraredProtocolType


@dataclass(frozen=True, slots=True)
class PulseWidthIRProtocol(InfraredProtocol):
    """Pulse-width modulated IR protocol.

    Defines timing for header, one bit, zero bit, and footer.
    Used to convert a numeric code into raw timing data.

    Attributes:
        header: Timing for the header pulse.
        one: Timing for a '1' bit.
        zero: Timing for a '0' bit.
        footer: Timing for the footer pulse.
        frequency: Carrier frequency in Hz (e.g., 38000 for 38kHz).
        msb_first: If True, send most significant bit first (default for most protocols).
        minimum_idle_time_us: Minimum gap between transmissions in microseconds.
    """

    type = InfraredProtocolType.PULSE_WIDTH

    header: IRTiming
    one: IRTiming
    zero: IRTiming
    footer: IRTiming
    frequency: int = 38000
    msb_first: bool = True
    minimum_idle_time_us: int = 0


@dataclass(frozen=True, slots=True)
class NECInfraredProtocol(InfraredProtocol):
    """NEC IR protocol."""

    type = InfraredProtocolType.NEC

    def get_pulse_width_compat_protocol(self) -> PulseWidthIRProtocol:
        """Convert to a PulseWidthIRProtocol for encoding."""
        return PulseWidthIRProtocol(
            header=IRTiming(high_us=9000, low_us=4500),
            one=IRTiming(high_us=560, low_us=1690),
            zero=IRTiming(high_us=560, low_us=560),
            footer=IRTiming(high_us=560, low_us=0),
            msb_first=False,
            minimum_idle_time_us=40000,
        )


@dataclass(frozen=True, slots=True)
class SamsungInfraredProtocol(InfraredProtocol):
    """Samsung 32-bit IR protocol."""

    type = InfraredProtocolType.SAMSUNG

    def get_pulse_width_compat_protocol(self) -> PulseWidthIRProtocol:
        """Convert to a PulseWidthIRProtocol for encoding."""
        return PulseWidthIRProtocol(
            header=IRTiming(high_us=4500, low_us=4500),
            one=IRTiming(high_us=560, low_us=1690),
            zero=IRTiming(high_us=560, low_us=560),
            footer=IRTiming(high_us=560, low_us=0),
            msb_first=False,
            minimum_idle_time_us=0,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class InfraredCommand:
    """Base class for IR commands."""

    repeat_count: int
    protocol: InfraredProtocol


@dataclass(frozen=True, slots=True, kw_only=True)
class PulseWidthInfraredCommand(InfraredCommand):
    """IR command with a numeric code for pulse-width protocols."""

    code: int
    length_in_bits: int
    protocol: PulseWidthIRProtocol


@dataclass(frozen=True, slots=True, kw_only=True)
class NECInfraredCommand(InfraredCommand):
    """NEC IR command."""

    address: int
    command: int
    protocol: NECInfraredProtocol = field(default_factory=NECInfraredProtocol)

    def get_pulse_width_compat_code(self) -> int:
        """Return the code in pulse-width compatible 32-bit format."""
        addr = self.address & 0xFFFF
        cmd = self.command & 0xFFFF
        return addr | (cmd << 16)


@dataclass(frozen=True, slots=True, kw_only=True)
class SamsungInfraredCommand(InfraredCommand):
    """Samsung IR command."""

    code: int
    length_in_bits: int = 32
    protocol: SamsungInfraredProtocol = field(default_factory=SamsungInfraredProtocol)

    def get_pulse_width_compat_code(self) -> int:
        """Return the code in pulse-width compatible format.

        Samsung codes are already 32-bit integers, so no conversion is needed.
        """
        return self.code
