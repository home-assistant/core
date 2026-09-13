"""Tests for the NeoPool helper functions."""

import pytest

from homeassistant.components.neopool.helpers import parse_register_int
from homeassistant.exceptions import ServiceValidationError


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1539", 1539),
        ("0x0603", 0x0603),
        (0, 0),
        (65535, 65535),
        ("0", 0),
        ("0xFFFF", 0xFFFF),
    ],
)
def test_parse_register_int_valid(raw: int | str, expected: int) -> None:
    """parse_register_int accepts decimal and 0x-prefixed strings as well as ints."""
    assert parse_register_int(raw, "address") == expected


def test_parse_register_int_rejects_bool() -> None:
    """A bare bool must not silently coerce to 0/1."""
    with pytest.raises(ServiceValidationError) as exc_info:
        parse_register_int(True, "address")
    assert exc_info.value.translation_key == "invalid_register_type"


def test_parse_register_int_rejects_float() -> None:
    """A float would lose precision; reject it explicitly."""
    with pytest.raises(ServiceValidationError) as exc_info:
        parse_register_int(1.5, "address")
    assert exc_info.value.translation_key == "invalid_register_float"


@pytest.mark.parametrize("raw", ["nonsense", "", "0xZZZZ"])
def test_parse_register_int_rejects_unparsable(raw: str) -> None:
    """Unparsable strings raise ServiceValidationError."""
    with pytest.raises(ServiceValidationError) as exc_info:
        parse_register_int(raw, "address")
    assert exc_info.value.translation_key == "invalid_register_type"


@pytest.mark.parametrize("raw", [-1, 65536, "0x10000"])
def test_parse_register_int_rejects_out_of_range(raw: int | str) -> None:
    """Values outside the 16-bit holding-register range are rejected."""
    with pytest.raises(ServiceValidationError) as exc_info:
        parse_register_int(raw, "value")
    assert exc_info.value.translation_key == "register_out_of_range"
