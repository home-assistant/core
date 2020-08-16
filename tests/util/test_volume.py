"""Test Home Assistant volume utility functions."""

import pytest

from homeassistant.const import (
    VOLUME_FLUID_OUNCE,
    VOLUME_GALLONS,
    VOLUME_LITERS,
    VOLUME_MILLILITERS,
)
import homeassistant.util.volume as volume_util

INVALID_SYMBOL = "bob"
VALID_SYMBOL = VOLUME_LITERS


def test_convert_same_unit():
    """Test conversion from any unit to same unit."""
    assert volume_util.convert(2, VOLUME_LITERS, VOLUME_LITERS) == 2
    assert volume_util.convert(3, VOLUME_MILLILITERS, VOLUME_MILLILITERS) == 3
    assert volume_util.convert(4, VOLUME_GALLONS, VOLUME_GALLONS) == 4
    assert volume_util.convert(5, VOLUME_FLUID_OUNCE, VOLUME_FLUID_OUNCE) == 5


def test_convert_invalid_unit():
    """Test exception is thrown for invalid units."""
    with pytest.raises(ValueError):
        volume_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

    with pytest.raises(ValueError):
        volume_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)


def test_convert_nonnumeric_value():
    """Test exception is thrown for nonnumeric type."""
    with pytest.raises(TypeError):
        volume_util.convert("a", VOLUME_GALLONS, VOLUME_LITERS)


def test_convert_from_liters():
    """Test conversion from liters to other units."""
    liters = 5
    assert volume_util.convert(liters, VOLUME_LITERS, VOLUME_GALLONS) == 1.321


def test_convert_from_gallons():
    """Test conversion from gallons to other units."""
    gallons = 5
    assert volume_util.convert(gallons, VOLUME_GALLONS, VOLUME_LITERS) == 18.925
