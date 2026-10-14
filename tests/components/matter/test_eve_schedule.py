"""Tests for the proprietary Eve Thermo schedule status decoder."""

import base64

import pytest

from homeassistant.components.matter.binary_sensor import _eve_thermo_schedule_enabled


@pytest.mark.parametrize(
    ("flag", "expected"),
    [(0x0C, False), (0x0D, True), (0x0E, False), (0x0F, True)],
)
def test_eve_thermo_schedule_flag(flag: int, expected: bool) -> None:
    """Only the low bit of the observed configuration byte determines state."""
    payload = bytearray(275)
    payload[211] = flag
    assert _eve_thermo_schedule_enabled(bytes(payload)) is expected
    assert _eve_thermo_schedule_enabled(base64.b64encode(payload).decode()) is expected


@pytest.mark.parametrize(
    "payload", [b"", b"invalid", bytes(274), bytes(276), "not base64!", 42]
)
def test_eve_thermo_schedule_invalid(payload: bytes | str | int) -> None:
    """Unknown payload formats must not report a false off state."""
    assert _eve_thermo_schedule_enabled(payload) is None
