"""Test Home Assistant temperature utility functions."""

import pytest

from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
import homeassistant.util.temperature as temperature_util

INVALID_SYMBOL = "bob"
VALID_SYMBOL = TEMP_CELSIUS


def test_convert_same_unit():
    """Test conversion from any unit to same unit."""
    assert temperature_util.convert(2, TEMP_CELSIUS, TEMP_CELSIUS) == 2
    assert temperature_util.convert(3, TEMP_FAHRENHEIT, TEMP_FAHRENHEIT) == 3


def test_convert_invalid_unit():
    """Test exception is thrown for invalid units."""
    with pytest.raises(ValueError):
        temperature_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

    with pytest.raises(ValueError):
        temperature_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)


def test_convert_nonnumeric_value():
    """Test exception is thrown for nonnumeric type."""
    with pytest.raises(TypeError):
        temperature_util.convert("a", TEMP_CELSIUS, TEMP_FAHRENHEIT)


def test_convert_from_celsius():
    """Test conversion from liters to other units."""
    celsius = 26
    assert temperature_util.convert(celsius, TEMP_CELSIUS, TEMP_FAHRENHEIT) == 78.8
    assert (
        temperature_util.convert(celsius, TEMP_CELSIUS, TEMP_FAHRENHEIT, interval=True)
        == 46.8
    )


def test_convert_from_fahrenheit():
    """Test conversion from gallons to other units."""
    fahrenheit = 100
    assert temperature_util.convert(fahrenheit, TEMP_FAHRENHEIT, TEMP_CELSIUS) == 37.8
    assert (
        temperature_util.convert(
            fahrenheit, TEMP_FAHRENHEIT, TEMP_CELSIUS, interval=True
        )
        == 55.6
    )
