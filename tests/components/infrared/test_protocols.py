"""Tests for the Infrared protocol definitions."""

import pytest

from homeassistant.components.infrared import (
    InfraredProtocolType,
    IRTiming,
    NECInfraredCommand,
    NECInfraredProtocol,
    SamsungInfraredCommand,
    SamsungInfraredProtocol,
)


def test_nec_protocol_pulse_width_compat() -> None:
    """Test NEC protocol conversion to pulse-width compatible format."""
    protocol = NECInfraredProtocol()
    compat = protocol.get_pulse_width_compat_protocol()

    # Verify timing values match NEC standard
    assert compat.header.high_us == 9000
    assert compat.header.low_us == 4500
    assert compat.one.high_us == 560
    assert compat.one.low_us == 1690
    assert compat.zero.high_us == 560
    assert compat.zero.low_us == 560
    assert compat.footer.high_us == 560
    assert compat.footer.low_us == 0
    assert compat.frequency == 38000
    assert compat.msb_first is False
    assert compat.minimum_idle_time_us == 40000


def test_samsung_protocol_pulse_width_compat() -> None:
    """Test Samsung protocol conversion to pulse-width compatible format."""
    protocol = SamsungInfraredProtocol()
    compat = protocol.get_pulse_width_compat_protocol()

    # Verify timing values match Samsung standard
    assert compat.header.high_us == 4500
    assert compat.header.low_us == 4500
    assert compat.one.high_us == 560
    assert compat.one.low_us == 1690
    assert compat.zero.high_us == 560
    assert compat.zero.low_us == 560
    assert compat.frequency == 38000


def test_nec_command_pulse_width_compat_code() -> None:
    """Test NEC command code conversion to pulse-width format."""
    command = NECInfraredCommand(
        repeat_count=1,
        address=0x04FB,  # 16-bit address
        command=0x08F7,  # 16-bit command
    )

    # Code should be: address | (command << 16)
    expected_code = 0x04FB | (0x08F7 << 16)
    assert command.get_pulse_width_compat_code() == expected_code


def test_samsung_command_pulse_width_compat_code() -> None:
    """Test Samsung command code conversion (should be passthrough)."""
    command = SamsungInfraredCommand(
        repeat_count=1,
        code=0xE0E040BF,
        length_in_bits=32,
    )

    # Samsung code should pass through unchanged
    assert command.get_pulse_width_compat_code() == 0xE0E040BF


def test_ir_timing_frozen() -> None:
    """Test that IRTiming is immutable."""
    timing = IRTiming(high_us=9000, low_us=4500)

    with pytest.raises(AttributeError):
        timing.high_us = 1000  # type: ignore[misc]


def test_nec_command_frozen() -> None:
    """Test that NECIRCommand is immutable."""
    command = NECInfraredCommand(
        repeat_count=1,
        address=0x04FB,
        command=0x08F7,
    )

    with pytest.raises(AttributeError):
        command.address = 0x0000  # type: ignore[misc]


def test_protocol_types() -> None:
    """Test protocol type enum values."""
    assert InfraredProtocolType.PULSE_WIDTH == "pulse_width"
    assert InfraredProtocolType.NEC == "nec"
    assert InfraredProtocolType.SAMSUNG == "samsung"
