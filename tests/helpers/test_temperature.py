"""Tests Home Assistant temperature helpers."""
import pytest

from homeassistant.const import (
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.temperature import display_temp

TEMP = 24.636626


def test_temperature_not_a_number(hass: HomeAssistant) -> None:
    """Test that temperature is a number."""
    temp = "Temperature"
    with pytest.raises(Exception) as exception:
        display_temp(hass, temp, TEMP_CELSIUS, PRECISION_HALVES)

    assert f"Temperature is not a number: {temp}" in str(exception.value)


def test_celsius_halves(hass: HomeAssistant) -> None:
    """Test temperature to celsius rounding to halves."""
    assert display_temp(hass, TEMP, TEMP_CELSIUS, PRECISION_HALVES) == 24.5


def test_celsius_tenths(hass: HomeAssistant) -> None:
    """Test temperature to celsius rounding to tenths."""
    assert display_temp(hass, TEMP, TEMP_CELSIUS, PRECISION_TENTHS) == 24.6


def test_fahrenheit_wholes(hass: HomeAssistant) -> None:
    """Test temperature to fahrenheit rounding to wholes."""
    assert display_temp(hass, TEMP, TEMP_FAHRENHEIT, PRECISION_WHOLE) == -4
