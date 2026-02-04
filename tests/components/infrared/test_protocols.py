"""Tests for the Infrared protocol definitions."""

from homeassistant.components.infrared import NECInfraredCommand, Timing


def test_nec_command_get_raw_timings_standard() -> None:
    """Test NEC command raw timings generation for standard 8-bit address."""
    expected_raw_timings = [
        Timing(high_us=9000, low_us=4500),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=0),
    ]
    command = NECInfraredCommand(
        address=0x04, command=0x08, modulation=38000, repeat_count=0
    )
    timings = command.get_raw_timings()
    assert timings == expected_raw_timings

    # Same command now with 2 repeats
    command_with_repeats = NECInfraredCommand(
        address=command.address,
        command=command.command,
        modulation=command.modulation,
        repeat_count=2,
    )
    timings_with_repeats = command_with_repeats.get_raw_timings()
    assert timings_with_repeats == [
        *expected_raw_timings[:-1],
        Timing(high_us=562, low_us=96000),
        Timing(high_us=9000, low_us=2250),
        Timing(high_us=562, low_us=96000),
        Timing(high_us=9000, low_us=2250),
        Timing(high_us=562, low_us=0),
    ]


def test_nec_command_get_raw_timings_extended() -> None:
    """Test NEC command raw timings generation for extended 16-bit address."""
    expected_raw_timings = [
        Timing(high_us=9000, low_us=4500),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=562),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=1687),
        Timing(high_us=562, low_us=0),
    ]

    command = NECInfraredCommand(
        address=0x04FB, command=0x08, modulation=38000, repeat_count=0
    )
    timings = command.get_raw_timings()
    assert timings == expected_raw_timings

    # Same command now with 2 repeats
    command_with_repeats = NECInfraredCommand(
        address=command.address,
        command=command.command,
        modulation=command.modulation,
        repeat_count=2,
    )
    timings_with_repeats = command_with_repeats.get_raw_timings()
    assert timings_with_repeats == [
        *expected_raw_timings[:-1],
        Timing(high_us=562, low_us=96000),
        Timing(high_us=9000, low_us=2250),
        Timing(high_us=562, low_us=96000),
        Timing(high_us=9000, low_us=2250),
        Timing(high_us=562, low_us=0),
    ]
