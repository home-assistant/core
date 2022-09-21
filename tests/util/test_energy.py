"""Test Home Assistant eneergy utility functions."""
import pytest

from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    ENERGY_MEGA_WATT_HOUR,
    ENERGY_WATT_HOUR,
)
import homeassistant.util.energy as energy_util

INVALID_SYMBOL = "bob"
VALID_SYMBOL = ENERGY_KILO_WATT_HOUR


def test_convert_same_unit():
    """Test conversion from any unit to same unit."""
    assert energy_util.convert(2, ENERGY_WATT_HOUR, ENERGY_WATT_HOUR) == 2
    assert energy_util.convert(3, ENERGY_KILO_WATT_HOUR, ENERGY_KILO_WATT_HOUR) == 3
    assert energy_util.convert(4, ENERGY_MEGA_WATT_HOUR, ENERGY_MEGA_WATT_HOUR) == 4


def test_convert_invalid_unit():
    """Test exception is thrown for invalid units."""
    with pytest.raises(ValueError):
        energy_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

    with pytest.raises(ValueError):
        energy_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)


def test_convert_nonnumeric_value():
    """Test exception is thrown for nonnumeric type."""
    with pytest.raises(TypeError):
        energy_util.convert("a", ENERGY_WATT_HOUR, ENERGY_KILO_WATT_HOUR)


def test_convert_from_wh():
    """Test conversion from Wh to other units."""
    watthours = 10
    assert (
        energy_util.convert(watthours, ENERGY_WATT_HOUR, ENERGY_KILO_WATT_HOUR) == 0.01
    )
    assert (
        energy_util.convert(watthours, ENERGY_WATT_HOUR, ENERGY_MEGA_WATT_HOUR)
        == 0.00001
    )


def test_convert_from_kwh():
    """Test conversion from kWh to other units."""
    kilowatthours = 10
    assert (
        energy_util.convert(kilowatthours, ENERGY_KILO_WATT_HOUR, ENERGY_WATT_HOUR)
        == 10000
    )
    assert (
        energy_util.convert(kilowatthours, ENERGY_KILO_WATT_HOUR, ENERGY_MEGA_WATT_HOUR)
        == 0.01
    )


def test_convert_from_mwh():
    """Test conversion from W to other units."""
    megawatthours = 10
    assert (
        energy_util.convert(megawatthours, ENERGY_MEGA_WATT_HOUR, ENERGY_WATT_HOUR)
        == 10000000
    )
    assert (
        energy_util.convert(megawatthours, ENERGY_MEGA_WATT_HOUR, ENERGY_KILO_WATT_HOUR)
        == 10000
    )
