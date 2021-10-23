"""Test Home Assistant speed utility functions."""
import pytest

from homeassistant.const import (
    SPEED_INCHES_PER_DAY,
    SPEED_INCHES_PER_HOUR,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    SPEED_MILLIMETERS_PER_DAY,
)
import homeassistant.util.speed as speed_util

INVALID_SYMBOL = "bob"
VALID_SYMBOL = SPEED_KILOMETERS_PER_HOUR


def test_convert_same_unit():
    """Test conversion from any unit to same unit."""
    assert speed_util.convert(2, SPEED_INCHES_PER_DAY, SPEED_INCHES_PER_DAY) == 2
    assert speed_util.convert(3, SPEED_INCHES_PER_HOUR, SPEED_INCHES_PER_HOUR) == 3
    assert (
        speed_util.convert(4, SPEED_KILOMETERS_PER_HOUR, SPEED_KILOMETERS_PER_HOUR) == 4
    )
    assert speed_util.convert(5, SPEED_METERS_PER_SECOND, SPEED_METERS_PER_SECOND) == 5
    assert speed_util.convert(6, SPEED_MILES_PER_HOUR, SPEED_MILES_PER_HOUR) == 6
    assert (
        speed_util.convert(7, SPEED_MILLIMETERS_PER_DAY, SPEED_MILLIMETERS_PER_DAY) == 7
    )


def test_convert_invalid_unit():
    """Test exception is thrown for invalid units."""
    with pytest.raises(ValueError):
        speed_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

    with pytest.raises(ValueError):
        speed_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)


def test_convert_nonnumeric_value():
    """Test exception is thrown for nonnumeric type."""
    with pytest.raises(TypeError):
        speed_util.convert("a", SPEED_KILOMETERS_PER_HOUR, SPEED_MILES_PER_HOUR)


def test_convert_from_kph():
    """Test conversion from kph to other units."""
    kph = 5
    assert (
        speed_util.convert(kph, SPEED_KILOMETERS_PER_HOUR, SPEED_MILES_PER_HOUR)
        == 3.106855972222222
    )


def test_convert_from_mph():
    """Test conversion from mph to other units."""
    mph = 5
    assert (
        speed_util.convert(mph, SPEED_MILES_PER_HOUR, SPEED_KILOMETERS_PER_HOUR)
        == 8.046719971418051
    )
