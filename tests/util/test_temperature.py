"""Test Home Assistant temperature utility functions."""
import pytest

from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT, TEMP_KELVIN
import homeassistant.util.temperature as temperature_util

INVALID_SYMBOL = "bob"
VALID_SYMBOL = TEMP_CELSIUS


def test_convert_same_unit():
    """Test conversion from any unit to same unit."""
    assert temperature_util.convert(2, TEMP_CELSIUS, TEMP_CELSIUS) == 2
    assert temperature_util.convert(3, TEMP_FAHRENHEIT, TEMP_FAHRENHEIT) == 3
    assert temperature_util.convert(4, TEMP_KELVIN, TEMP_KELVIN) == 4


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
    """Test conversion from C to other units."""
    celsius = 100
    assert temperature_util.convert(
        celsius, TEMP_CELSIUS, TEMP_FAHRENHEIT
    ) == pytest.approx(212.0)
    assert temperature_util.convert(
        celsius, TEMP_CELSIUS, TEMP_KELVIN
    ) == pytest.approx(373.15)
    # Interval
    assert temperature_util.convert(
        celsius, TEMP_CELSIUS, TEMP_FAHRENHEIT, True
    ) == pytest.approx(180.0)
    assert temperature_util.convert(
        celsius, TEMP_CELSIUS, TEMP_KELVIN, True
    ) == pytest.approx(100)


def test_convert_from_fahrenheit():
    """Test conversion from F to other units."""
    fahrenheit = 100
    assert temperature_util.convert(
        fahrenheit, TEMP_FAHRENHEIT, TEMP_CELSIUS
    ) == pytest.approx(37.77777777777778)
    assert temperature_util.convert(
        fahrenheit, TEMP_FAHRENHEIT, TEMP_KELVIN
    ) == pytest.approx(310.92777777777775)
    # Interval
    assert temperature_util.convert(
        fahrenheit, TEMP_FAHRENHEIT, TEMP_CELSIUS, True
    ) == pytest.approx(55.55555555555556)
    assert temperature_util.convert(
        fahrenheit, TEMP_FAHRENHEIT, TEMP_KELVIN, True
    ) == pytest.approx(55.55555555555556)


def test_convert_from_kelvin():
    """Test conversion from K to other units."""
    kelvin = 100
    assert temperature_util.convert(kelvin, TEMP_KELVIN, TEMP_CELSIUS) == pytest.approx(
        -173.15
    )
    assert temperature_util.convert(
        kelvin, TEMP_KELVIN, TEMP_FAHRENHEIT
    ) == pytest.approx(-279.66999999999996)
    # Interval
    assert temperature_util.convert(
        kelvin, TEMP_KELVIN, TEMP_FAHRENHEIT, True
    ) == pytest.approx(180.0)
    assert temperature_util.convert(
        kelvin, TEMP_KELVIN, TEMP_KELVIN, True
    ) == pytest.approx(100)
