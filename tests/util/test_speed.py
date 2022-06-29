"""Test Home Assistant speed utility functions."""
import pytest

from homeassistant.const import (
    SPEED_FEET_PER_SECOND,
    SPEED_INCHES_PER_DAY,
    SPEED_INCHES_PER_HOUR,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_KNOTS,
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


@pytest.mark.parametrize(
    "from_value, from_unit, expected, to_unit",
    [
        # 5 km/h / 1.609 km/mi = 3.10686 mi/h
        (5, SPEED_KILOMETERS_PER_HOUR, 3.10686, SPEED_MILES_PER_HOUR),
        # 5 mi/h * 1.609 km/mi = 8.04672 km/h
        (5, SPEED_MILES_PER_HOUR, 8.04672, SPEED_KILOMETERS_PER_HOUR),
        # 5 in/day * 25.4 mm/in = 127 mm/day
        (5, SPEED_INCHES_PER_DAY, 127, SPEED_MILLIMETERS_PER_DAY),
        # 5 mm/day / 25.4 mm/in = 0.19685 in/day
        (5, SPEED_MILLIMETERS_PER_DAY, 0.19685, SPEED_INCHES_PER_DAY),
        # 5 in/hr * 24 hr/day = 3048 mm/day
        (5, SPEED_INCHES_PER_HOUR, 3048, SPEED_MILLIMETERS_PER_DAY),
        # 5 m/s * 39.3701 in/m * 3600 s/hr = 708661
        (5, SPEED_METERS_PER_SECOND, 708661, SPEED_INCHES_PER_HOUR),
        # 5000 in/h / 39.3701 in/m / 3600 s/h = 0.03528 m/s
        (5000, SPEED_INCHES_PER_HOUR, 0.03528, SPEED_METERS_PER_SECOND),
        # 5 kt * 1852 m/nmi / 3600 s/h = 2.5722 m/s
        (5, SPEED_KNOTS, 2.5722, SPEED_METERS_PER_SECOND),
        # 5 ft/s * 0.3048 m/ft = 1.524 m/s
        (5, SPEED_FEET_PER_SECOND, 1.524, SPEED_METERS_PER_SECOND),
    ],
)
def test_convert_different_units(from_value, from_unit, expected, to_unit):
    """Test conversion between units."""
    assert speed_util.convert(from_value, from_unit, to_unit) == pytest.approx(
        expected, rel=1e-4
    )
