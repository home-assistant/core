"""Test AirTouch 3 command message generation."""

import logging

import pytest

from homeassistant.components.airtouch3.comms.airtouch_message import AirTouchMessage


def test_message_reset_and_checksum() -> None:
    """Test the base message buffer and checksum calculation."""
    message = AirTouchMessage()
    message.buffer[:] = b"\xff" * 13

    message.reset_message()

    assert message.buffer == bytearray([85, 0, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    assert message.calc_checksum() == 97


def test_message_init_and_temperature_flag() -> None:
    """Test the init message and temperature flag accessors."""
    message = AirTouchMessage()

    message.is_temp = True

    assert message.is_temp is True
    assert message.get_init_msg() == bytearray(
        [85, 1, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 98]
    )


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (
            AirTouchMessage().toggle_zone(3),
            bytearray([85, 129, 12, 3, 128, 0, 0, 0, 0, 0, 0, 0, 101]),
        ),
        (
            AirTouchMessage().set_fan(2, 1),
            bytearray([85, 129, 12, 2, 2, 1, 0, 0, 0, 0, 0, 0, 231]),
        ),
        (
            AirTouchMessage().set_fan(2, -1),
            bytearray([85, 129, 12, 2, 1, 1, 0, 0, 0, 0, 0, 0, 230]),
        ),
        (
            AirTouchMessage().toggle_ac_on_off(1),
            bytearray([85, 134, 12, 1, 128, 0, 0, 0, 0, 0, 0, 0, 104]),
        ),
    ],
)
def test_message_commands(command: bytearray, expected: bytearray) -> None:
    """Test fixed AirTouch command buffers."""
    assert command == expected


@pytest.mark.parametrize(
    ("brand_id", "mode", "expected_mode", "expected_checksum"),
    [
        (0, 4, 4, 108),
        (11, 1, 2, 106),
        (15, 0, 5, 109),
    ],
)
def test_set_mode_brand_mapping(
    brand_id: int, mode: int, expected_mode: int, expected_checksum: int
) -> None:
    """Test mode command brand remapping."""
    command = AirTouchMessage().set_mode(0, brand_id, mode)

    assert command[5] == expected_mode
    assert command[12] == expected_checksum


@pytest.mark.parametrize(
    ("brand_id", "mode", "expected_mode", "expected_checksum"),
    [
        (0, 2, 2, 107),
        (15, 0, 4, 109),
        (2, 4, 1, 106),
        (2, 2, 3, 108),
    ],
)
def test_set_fan_speed_brand_mapping(
    brand_id: int, mode: int, expected_mode: int, expected_checksum: int
) -> None:
    """Test fan speed command brand remapping."""
    command = AirTouchMessage().set_fan_speed(0, brand_id, mode)

    assert command[5] == expected_mode
    assert command[12] == expected_checksum


def test_print_hex_code(caplog: pytest.LogCaptureFixture) -> None:
    """Test message debug logging."""
    message = AirTouchMessage()
    message.reset_message()

    with caplog.at_level(logging.DEBUG):
        message.print_hex_code()

    assert "55,00,0c,00,00,00,00,00,00,00,00,00,00" in caplog.text
