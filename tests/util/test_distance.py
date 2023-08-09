"""Test Home Assistant distance utility functions."""

import pytest

from homeassistant.const import (
    UnitOfLength,
)
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.distance as distance_util

INVALID_SYMBOL = "bob"
VALID_SYMBOL = UnitOfLength.KILOMETERS


def test_raise_deprecation_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Ensure that a warning is raised on use of convert."""
    assert distance_util.convert(2, UnitOfLength.METERS, UnitOfLength.METERS) == 2
    assert "use unit_conversion.DistanceConverter instead" in caplog.text


def test_convert_same_unit() -> None:
    """Test conversion from any unit to same unit."""
    assert (
        distance_util.convert(5, UnitOfLength.KILOMETERS, UnitOfLength.KILOMETERS) == 5
    )
    assert distance_util.convert(2, UnitOfLength.METERS, UnitOfLength.METERS) == 2
    assert (
        distance_util.convert(6, UnitOfLength.CENTIMETERS, UnitOfLength.CENTIMETERS)
        == 6
    )
    assert (
        distance_util.convert(3, UnitOfLength.MILLIMETERS, UnitOfLength.MILLIMETERS)
        == 3
    )
    assert distance_util.convert(10, UnitOfLength.MILES, UnitOfLength.MILES) == 10
    assert distance_util.convert(9, UnitOfLength.YARDS, UnitOfLength.YARDS) == 9
    assert distance_util.convert(8, UnitOfLength.FEET, UnitOfLength.FEET) == 8
    assert distance_util.convert(7, UnitOfLength.INCHES, UnitOfLength.INCHES) == 7


def test_convert_invalid_unit() -> None:
    """Test exception is thrown for invalid units."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        distance_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        distance_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)


def test_convert_nonnumeric_value() -> None:
    """Test exception is thrown for nonnumeric type."""
    with pytest.raises(TypeError):
        distance_util.convert("a", UnitOfLength.KILOMETERS, UnitOfLength.METERS)


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        (UnitOfLength.KILOMETERS, 8.04672),
        (UnitOfLength.METERS, 8046.72),
        (UnitOfLength.CENTIMETERS, 804672.0),
        (UnitOfLength.MILLIMETERS, 8046720.0),
        (UnitOfLength.YARDS, 8800.0),
        (UnitOfLength.FEET, 26400.0008448),
        (UnitOfLength.INCHES, 316800.171072),
    ],
)
def test_convert_from_miles(unit, expected) -> None:
    """Test conversion from miles to other units."""
    miles = 5
    assert distance_util.convert(miles, UnitOfLength.MILES, unit) == pytest.approx(
        expected
    )


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        (UnitOfLength.KILOMETERS, 0.0045720000000000005),
        (UnitOfLength.METERS, 4.572),
        (UnitOfLength.CENTIMETERS, 457.2),
        (UnitOfLength.MILLIMETERS, 4572),
        (UnitOfLength.MILES, 0.002840908212),
        (UnitOfLength.FEET, 15.00000048),
        (UnitOfLength.INCHES, 180.0000972),
    ],
)
def test_convert_from_yards(unit, expected) -> None:
    """Test conversion from yards to other units."""
    yards = 5
    assert distance_util.convert(yards, UnitOfLength.YARDS, unit) == pytest.approx(
        expected
    )


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        (UnitOfLength.KILOMETERS, 1.524),
        (UnitOfLength.METERS, 1524),
        (UnitOfLength.CENTIMETERS, 152400.0),
        (UnitOfLength.MILLIMETERS, 1524000.0),
        (UnitOfLength.MILES, 0.9469694040000001),
        (UnitOfLength.YARDS, 1666.66667),
        (UnitOfLength.INCHES, 60000.032400000004),
    ],
)
def test_convert_from_feet(unit, expected) -> None:
    """Test conversion from feet to other units."""
    feet = 5000
    assert distance_util.convert(feet, UnitOfLength.FEET, unit) == pytest.approx(
        expected
    )


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        (UnitOfLength.KILOMETERS, 0.127),
        (UnitOfLength.METERS, 127.0),
        (UnitOfLength.CENTIMETERS, 12700.0),
        (UnitOfLength.MILLIMETERS, 127000.0),
        (UnitOfLength.MILES, 0.078914117),
        (UnitOfLength.YARDS, 138.88889),
        (UnitOfLength.FEET, 416.66668),
    ],
)
def test_convert_from_inches(unit, expected) -> None:
    """Test conversion from inches to other units."""
    inches = 5000
    assert distance_util.convert(inches, UnitOfLength.INCHES, unit) == pytest.approx(
        expected
    )


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        (UnitOfLength.METERS, 5000),
        (UnitOfLength.CENTIMETERS, 500000),
        (UnitOfLength.MILLIMETERS, 5000000),
        (UnitOfLength.MILES, 3.106855),
        (UnitOfLength.YARDS, 5468.066),
        (UnitOfLength.FEET, 16404.2),
        (UnitOfLength.INCHES, 196850.5),
    ],
)
def test_convert_from_kilometers(unit, expected) -> None:
    """Test conversion from kilometers to other units."""
    km = 5
    assert distance_util.convert(km, UnitOfLength.KILOMETERS, unit) == pytest.approx(
        expected
    )


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        (UnitOfLength.KILOMETERS, 5),
        (UnitOfLength.CENTIMETERS, 500000),
        (UnitOfLength.MILLIMETERS, 5000000),
        (UnitOfLength.MILES, 3.106855),
        (UnitOfLength.YARDS, 5468.066),
        (UnitOfLength.FEET, 16404.2),
        (UnitOfLength.INCHES, 196850.5),
    ],
)
def test_convert_from_meters(unit, expected) -> None:
    """Test conversion from meters to other units."""
    m = 5000
    assert distance_util.convert(m, UnitOfLength.METERS, unit) == pytest.approx(
        expected
    )


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        (UnitOfLength.KILOMETERS, 5),
        (UnitOfLength.METERS, 5000),
        (UnitOfLength.MILLIMETERS, 5000000),
        (UnitOfLength.MILES, 3.106855),
        (UnitOfLength.YARDS, 5468.066),
        (UnitOfLength.FEET, 16404.2),
        (UnitOfLength.INCHES, 196850.5),
    ],
)
def test_convert_from_centimeters(unit, expected) -> None:
    """Test conversion from centimeters to other units."""
    cm = 500000
    assert distance_util.convert(cm, UnitOfLength.CENTIMETERS, unit) == pytest.approx(
        expected
    )


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        (UnitOfLength.KILOMETERS, 5),
        (UnitOfLength.METERS, 5000),
        (UnitOfLength.CENTIMETERS, 500000),
        (UnitOfLength.MILES, 3.106855),
        (UnitOfLength.YARDS, 5468.066),
        (UnitOfLength.FEET, 16404.2),
        (UnitOfLength.INCHES, 196850.5),
    ],
)
def test_convert_from_millimeters(unit, expected) -> None:
    """Test conversion from millimeters to other units."""
    mm = 5000000
    assert distance_util.convert(mm, UnitOfLength.MILLIMETERS, unit) == pytest.approx(
        expected
    )
