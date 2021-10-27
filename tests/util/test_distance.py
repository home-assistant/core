"""Test Home Assistant distance utility functions."""

import pytest

from homeassistant.const import (
    LENGTH_CENTIMETERS,
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    LENGTH_YARD,
)
import homeassistant.util.distance as distance_util

INVALID_SYMBOL = "bob"
VALID_SYMBOL = LENGTH_KILOMETERS


def test_convert_same_unit():
    """Test conversion from any unit to same unit."""
    assert distance_util.convert(5, LENGTH_KILOMETERS, LENGTH_KILOMETERS) == 5
    assert distance_util.convert(2, LENGTH_METERS, LENGTH_METERS) == 2
    assert distance_util.convert(6, LENGTH_CENTIMETERS, LENGTH_CENTIMETERS) == 6
    assert distance_util.convert(3, LENGTH_MILLIMETERS, LENGTH_MILLIMETERS) == 3
    assert distance_util.convert(10, LENGTH_MILES, LENGTH_MILES) == 10
    assert distance_util.convert(9, LENGTH_YARD, LENGTH_YARD) == 9
    assert distance_util.convert(8, LENGTH_FEET, LENGTH_FEET) == 8
    assert distance_util.convert(7, LENGTH_INCHES, LENGTH_INCHES) == 7


def test_convert_invalid_unit():
    """Test exception is thrown for invalid units."""
    with pytest.raises(ValueError):
        distance_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

    with pytest.raises(ValueError):
        distance_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)


def test_convert_nonnumeric_value():
    """Test exception is thrown for nonnumeric type."""
    with pytest.raises(TypeError):
        distance_util.convert("a", LENGTH_KILOMETERS, LENGTH_METERS)


def test_convert_from_miles():
    """Test conversion from miles to other units."""
    miles = 5
    assert distance_util.convert(miles, LENGTH_MILES, LENGTH_KILOMETERS) == 8.04672
    assert distance_util.convert(miles, LENGTH_MILES, LENGTH_METERS) == 8046.72
    assert distance_util.convert(miles, LENGTH_MILES, LENGTH_CENTIMETERS) == 804672.0
    assert distance_util.convert(miles, LENGTH_MILES, LENGTH_MILLIMETERS) == 8046720.0
    assert distance_util.convert(miles, LENGTH_MILES, LENGTH_YARD) == 8799.9734592
    assert distance_util.convert(miles, LENGTH_MILES, LENGTH_FEET) == 26400.0008448
    assert distance_util.convert(miles, LENGTH_MILES, LENGTH_INCHES) == 316800.171072


def test_convert_from_yards():
    """Test conversion from yards to other units."""
    yards = 5
    assert (
        distance_util.convert(yards, LENGTH_YARD, LENGTH_KILOMETERS)
        == 0.0045720000000000005
    )
    assert distance_util.convert(yards, LENGTH_YARD, LENGTH_METERS) == 4.572
    assert distance_util.convert(yards, LENGTH_YARD, LENGTH_CENTIMETERS) == 457.2
    assert distance_util.convert(yards, LENGTH_YARD, LENGTH_MILLIMETERS) == 4572.0
    assert distance_util.convert(yards, LENGTH_YARD, LENGTH_MILES) == 0.002840908212
    assert distance_util.convert(yards, LENGTH_YARD, LENGTH_FEET) == 15.00000048
    assert distance_util.convert(yards, LENGTH_YARD, LENGTH_INCHES) == 180.0000972


def test_convert_from_feet():
    """Test conversion from feet to other units."""
    feet = 5000
    assert distance_util.convert(feet, LENGTH_FEET, LENGTH_KILOMETERS) == 1.524
    assert distance_util.convert(feet, LENGTH_FEET, LENGTH_METERS) == 1524
    assert distance_util.convert(feet, LENGTH_FEET, LENGTH_CENTIMETERS) == 152400.0
    assert distance_util.convert(feet, LENGTH_FEET, LENGTH_MILLIMETERS) == 1524000.0
    assert distance_util.convert(feet, LENGTH_FEET, LENGTH_MILES) == 0.9469694040000001
    assert distance_util.convert(feet, LENGTH_FEET, LENGTH_YARD) == 1666.66164
    assert distance_util.convert(feet, LENGTH_FEET, LENGTH_INCHES) == 60000.032400000004


def test_convert_from_inches():
    """Test conversion from inches to other units."""
    inches = 5000
    assert distance_util.convert(inches, LENGTH_INCHES, LENGTH_KILOMETERS) == 0.127
    assert distance_util.convert(inches, LENGTH_INCHES, LENGTH_METERS) == 127.0
    assert distance_util.convert(inches, LENGTH_INCHES, LENGTH_CENTIMETERS) == 12700.0
    assert distance_util.convert(inches, LENGTH_INCHES, LENGTH_MILLIMETERS) == 127000.0
    assert distance_util.convert(inches, LENGTH_INCHES, LENGTH_MILES) == 0.078914117
    assert (
        distance_util.convert(inches, LENGTH_INCHES, LENGTH_YARD) == 138.88846999999998
    )
    assert distance_util.convert(inches, LENGTH_INCHES, LENGTH_FEET) == 416.66668


def test_convert_from_kilometers():
    """Test conversion from kilometers to other units."""
    km = 5
    assert distance_util.convert(km, LENGTH_KILOMETERS, LENGTH_METERS) == 5000
    assert distance_util.convert(km, LENGTH_KILOMETERS, LENGTH_CENTIMETERS) == 500000
    assert distance_util.convert(km, LENGTH_KILOMETERS, LENGTH_MILLIMETERS) == 5000000
    assert distance_util.convert(km, LENGTH_KILOMETERS, LENGTH_MILES) == 3.106855
    assert distance_util.convert(km, LENGTH_KILOMETERS, LENGTH_YARD) == 5468.05
    assert distance_util.convert(km, LENGTH_KILOMETERS, LENGTH_FEET) == 16404.2
    assert distance_util.convert(km, LENGTH_KILOMETERS, LENGTH_INCHES) == 196850.5


def test_convert_from_meters():
    """Test conversion from meters to other units."""
    m = 5000
    assert distance_util.convert(m, LENGTH_METERS, LENGTH_KILOMETERS) == 5
    assert distance_util.convert(m, LENGTH_METERS, LENGTH_CENTIMETERS) == 500000
    assert distance_util.convert(m, LENGTH_METERS, LENGTH_MILLIMETERS) == 5000000
    assert distance_util.convert(m, LENGTH_METERS, LENGTH_MILES) == 3.106855
    assert distance_util.convert(m, LENGTH_METERS, LENGTH_YARD) == 5468.05
    assert distance_util.convert(m, LENGTH_METERS, LENGTH_FEET) == 16404.2
    assert distance_util.convert(m, LENGTH_METERS, LENGTH_INCHES) == 196850.5


def test_convert_from_centimeters():
    """Test conversion from centimeters to other units."""
    cm = 500000
    assert distance_util.convert(cm, LENGTH_CENTIMETERS, LENGTH_KILOMETERS) == 5
    assert distance_util.convert(cm, LENGTH_CENTIMETERS, LENGTH_METERS) == 5000
    assert distance_util.convert(cm, LENGTH_CENTIMETERS, LENGTH_MILLIMETERS) == 5000000
    assert distance_util.convert(cm, LENGTH_CENTIMETERS, LENGTH_MILES) == 3.106855
    assert distance_util.convert(cm, LENGTH_CENTIMETERS, LENGTH_YARD) == 5468.05
    assert distance_util.convert(cm, LENGTH_CENTIMETERS, LENGTH_FEET) == 16404.2
    assert distance_util.convert(cm, LENGTH_CENTIMETERS, LENGTH_INCHES) == 196850.5


def test_convert_from_millimeters():
    """Test conversion from millimeters to other units."""
    mm = 5000000
    assert distance_util.convert(mm, LENGTH_MILLIMETERS, LENGTH_KILOMETERS) == 5
    assert distance_util.convert(mm, LENGTH_MILLIMETERS, LENGTH_METERS) == 5000
    assert distance_util.convert(mm, LENGTH_MILLIMETERS, LENGTH_CENTIMETERS) == 500000
    assert distance_util.convert(mm, LENGTH_MILLIMETERS, LENGTH_MILES) == 3.106855
    assert distance_util.convert(mm, LENGTH_MILLIMETERS, LENGTH_YARD) == 5468.05
    assert distance_util.convert(mm, LENGTH_MILLIMETERS, LENGTH_FEET) == 16404.2
    assert distance_util.convert(mm, LENGTH_MILLIMETERS, LENGTH_INCHES) == 196850.5
