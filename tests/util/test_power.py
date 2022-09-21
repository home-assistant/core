"""Test Home Assistant power utility functions."""
import pytest

from homeassistant.const import POWER_KILO_WATT, POWER_WATT
import homeassistant.util.power as power_util

INVALID_SYMBOL = "bob"
VALID_SYMBOL = POWER_WATT


def test_convert_same_unit():
    """Test conversion from any unit to same unit."""
    assert power_util.convert(2, POWER_WATT, POWER_WATT) == 2
    assert power_util.convert(3, POWER_KILO_WATT, POWER_KILO_WATT) == 3


def test_convert_invalid_unit():
    """Test exception is thrown for invalid units."""
    with pytest.raises(ValueError):
        power_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

    with pytest.raises(ValueError):
        power_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)


def test_convert_nonnumeric_value():
    """Test exception is thrown for nonnumeric type."""
    with pytest.raises(TypeError):
        power_util.convert("a", POWER_WATT, POWER_KILO_WATT)


def test_convert_from_kw():
    """Test conversion from kW to other units."""
    kilowatts = 10
    assert power_util.convert(kilowatts, POWER_KILO_WATT, POWER_WATT) == 10000


def test_convert_from_w():
    """Test conversion from W to other units."""
    watts = 10
    assert power_util.convert(watts, POWER_WATT, POWER_KILO_WATT) == 0.01
