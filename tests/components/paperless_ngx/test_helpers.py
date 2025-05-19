"""Tests for Paperless-ngx helpers."""

import pytest

from homeassistant.components.paperless_ngx.helpers import (
    build_state_fn,
    bytes_to_gb_converter,
    enum_values_to_lower,
)

from .conftest import TestEnum


class DummyState:
    """Dummy class with a value attribute."""

    def __init__(self, value) -> None:
        """Init dummy test class."""
        self.value = value


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        (1073741824, 1.07),
        (0, 0.0),
        (536870912, 0.54),
    ],
)
def test_bytes_to_gb_converter(input_value, expected) -> None:
    """Test byte-to-GB conversion."""
    assert bytes_to_gb_converter(input_value) == expected


def test_enum_values_to_lower() -> None:
    """Test enum value lowercase conversion."""
    expected = ["alpha", "beta", "gamma"]
    assert enum_values_to_lower(TestEnum) == expected


def test_build_state_fn_without_transform() -> None:
    """Test build_state_fn without transform."""

    def get_value(status: DummyState):
        return status.value

    fn = build_state_fn(get_value)
    assert fn(DummyState("abc")) == "abc"
    assert fn(DummyState(None)) is None


def test_build_state_fn_with_transform() -> None:
    """Test build_state_fn with transform."""

    def get_value(status: DummyState):
        return status.value

    def to_upper(value: str):
        return value.upper()

    fn = build_state_fn(get_value, to_upper)
    assert fn(DummyState("abc")) == "ABC"


def test_build_state_fn_with_none_input() -> None:
    """Test build_state_fn with None input."""
    fn = build_state_fn(lambda status: None)
    assert fn(DummyState("ignored")) is None
