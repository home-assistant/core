"""Test Home Assistant volume utility functions."""

import pytest

from homeassistant.const import (
    VOLUME_CUBIC_FEET,
    VOLUME_CUBIC_METERS,
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
    assert volume_util.convert(liters, VOLUME_LITERS, VOLUME_GALLONS) == pytest.approx(
        1.32086
    )


def test_convert_from_gallons():
    """Test conversion from gallons to other units."""
    gallons = 5
    assert volume_util.convert(gallons, VOLUME_GALLONS, VOLUME_LITERS) == pytest.approx(
        18.92706
    )


def test_convert_from_cubic_meters():
    """Test conversion from cubic meter to other units."""
    cubic_meters = 5
    assert volume_util.convert(
        cubic_meters, VOLUME_CUBIC_METERS, VOLUME_CUBIC_FEET
    ) == pytest.approx(176.5733335)


def test_convert_from_cubic_feet():
    """Test conversion from cubic feet to cubic meters to other units."""
    cubic_feets = 500
    assert volume_util.convert(
        cubic_feets, VOLUME_CUBIC_FEET, VOLUME_CUBIC_METERS
    ) == pytest.approx(14.1584233)


@pytest.mark.parametrize(
    "source_unit,target_unit,expected",
    [
        (VOLUME_CUBIC_FEET, VOLUME_CUBIC_METERS, 14.1584233),
        (VOLUME_CUBIC_FEET, VOLUME_FLUID_OUNCE, 478753.2467),
        (VOLUME_CUBIC_FEET, VOLUME_GALLONS, 3740.25974),
        (VOLUME_CUBIC_FEET, VOLUME_LITERS, 14158.42329599),
        (VOLUME_CUBIC_FEET, VOLUME_MILLILITERS, 14158423.29599),
        (VOLUME_CUBIC_METERS, VOLUME_CUBIC_METERS, 500),
        (VOLUME_CUBIC_METERS, VOLUME_FLUID_OUNCE, 16907011.35),
        (VOLUME_CUBIC_METERS, VOLUME_GALLONS, 132086.02617),
        (VOLUME_CUBIC_METERS, VOLUME_LITERS, 500000),
        (VOLUME_CUBIC_METERS, VOLUME_MILLILITERS, 500000000),
        (VOLUME_FLUID_OUNCE, VOLUME_CUBIC_FEET, 0.52218967),
        (VOLUME_FLUID_OUNCE, VOLUME_CUBIC_METERS, 0.014786764),
        (VOLUME_FLUID_OUNCE, VOLUME_GALLONS, 3.90625),
        (VOLUME_FLUID_OUNCE, VOLUME_LITERS, 14.786764),
        (VOLUME_FLUID_OUNCE, VOLUME_MILLILITERS, 14786.764),
        (VOLUME_GALLONS, VOLUME_CUBIC_FEET, 66.84027),
        (VOLUME_GALLONS, VOLUME_CUBIC_METERS, 1.892706),
        (VOLUME_GALLONS, VOLUME_FLUID_OUNCE, 64000),
        (VOLUME_GALLONS, VOLUME_LITERS, 1892.70589),
        (VOLUME_GALLONS, VOLUME_MILLILITERS, 1892705.89),
        (VOLUME_LITERS, VOLUME_CUBIC_FEET, 17.65733),
        (VOLUME_LITERS, VOLUME_CUBIC_METERS, 0.5),
        (VOLUME_LITERS, VOLUME_FLUID_OUNCE, 16907.011),
        (VOLUME_LITERS, VOLUME_GALLONS, 132.086),
        (VOLUME_LITERS, VOLUME_MILLILITERS, 500000),
        (VOLUME_MILLILITERS, VOLUME_CUBIC_FEET, 0.01765733),
        (VOLUME_MILLILITERS, VOLUME_CUBIC_METERS, 0.0005),
        (VOLUME_MILLILITERS, VOLUME_FLUID_OUNCE, 16.907),
        (VOLUME_MILLILITERS, VOLUME_GALLONS, 0.132086),
        (VOLUME_MILLILITERS, VOLUME_LITERS, 0.5),
    ],
)
def test_convert(source_unit, target_unit, expected):
    """Test conversion between units."""
    value = 500
    assert volume_util.convert(value, source_unit, target_unit) == pytest.approx(
        expected
    )
