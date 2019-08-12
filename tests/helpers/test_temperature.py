"""Tests Home Assistant temperature helpers."""
import pytest

from homeassistant.const import (
    TEMP_CELSIUS, PRECISION_WHOLE, TEMP_FAHRENHEIT, PRECISION_HALVES,
    PRECISION_TENTHS)
from homeassistant.helpers.temperature import display_temp

TEMP = 24.636626


def test_temperature_not_a_number(hass):
    """Test that temperature is a number."""
    temp = "Temperature"
    with pytest.raises(Exception) as exception:
        display_temp(hass, temp, TEMP_CELSIUS, PRECISION_HALVES)

    assert "Temperature is not a number: {}".format(temp) \
        in str(exception)


def test_celsius_halves(hass):
    """Test temperature to celsius rounding to halves."""
    assert display_temp(hass, TEMP, TEMP_CELSIUS, PRECISION_HALVES) == 24.5


def test_celsius_tenths(hass):
    """Test temperature to celsius rounding to tenths."""
    assert display_temp(hass, TEMP, TEMP_CELSIUS, PRECISION_TENTHS) == 24.6


def test_fahrenheit_wholes(hass):
    """Test temperature to fahrenheit rounding to wholes."""
    assert display_temp(hass, TEMP, TEMP_FAHRENHEIT, PRECISION_WHOLE) == -4
