"""Tests for the Infrared protocol definitions."""

import pytest

from homeassistant.components.infrared import (
    InfraredProtocol,
    NECInfraredCommand,
    Timing,
)


def test_nec_command_get_raw_timings_standard() -> None:
    """Test NEC command raw timings generation for standard 8-bit address."""
    command = NECInfraredCommand(
        address=0x04,
        command=0x08,
        repeat_count=0,
    )

    timings = command.get_raw_timings()

    # Leader pulse
    assert timings[0] == Timing(high_us=9000, low_us=4500)

    # 32 data bits + end pulse = 33 more timings after leader
    assert len(timings) == 34  # 1 leader + 32 data bits + 1 end pulse

    # End pulse (no repeat, so low_us = 0)
    assert timings[-1].high_us == 562
    assert timings[-1].low_us == 0


def test_nec_command_get_raw_timings_extended() -> None:
    """Test NEC command raw timings generation for extended 16-bit address."""
    command = NECInfraredCommand(
        address=0x04FB,  # 16-bit address
        command=0x08,
        repeat_count=0,
    )

    timings = command.get_raw_timings()

    # Leader pulse
    assert timings[0] == Timing(high_us=9000, low_us=4500)

    # 32 data bits + end pulse = 33 more timings after leader
    assert len(timings) == 34


def test_nec_command_get_raw_timings_with_repeat() -> None:
    """Test NEC command raw timings generation with repeat codes."""
    command = NECInfraredCommand(
        address=0x04,
        command=0x08,
        repeat_count=2,
    )

    timings = command.get_raw_timings()

    # Base: 1 leader + 32 data bits + 1 end pulse = 34
    # Each repeat: replaces last low_us with gap, adds leader + end pulse = +2
    # With 2 repeats: 34 + 2*2 = 38
    assert len(timings) == 38

    # Last timing should be end pulse with low_us=0
    assert timings[-1].high_us == 562
    assert timings[-1].low_us == 0


def test_nec_command_protocol_attribute() -> None:
    """Test NEC command has correct protocol attribute."""
    command = NECInfraredCommand(
        address=0x04,
        command=0x08,
    )

    assert command.protocol == InfraredProtocol.NEC


def test_timing_frozen() -> None:
    """Test that Timing is immutable."""
    timing = Timing(high_us=9000, low_us=4500)

    with pytest.raises(AttributeError):
        timing.high_us = 1000  # type: ignore[misc]


def test_protocol_types() -> None:
    """Test protocol type enum values."""
    assert InfraredProtocol.NEC == "nec"
    assert InfraredProtocol.SAMSUNG == "samsung"
