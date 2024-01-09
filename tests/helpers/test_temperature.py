"""Tests Home Assistant temperature helpers."""
import pytest

from homeassistant.const import Precision, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.temperature import display_temp

TEMP = 24.636626


def test_temperature_none(hass: HomeAssistant) -> None:
    """Test that temperature None returns None."""

    assert display_temp(hass, None, UnitOfTemperature.CELSIUS, Precision.WHOLE) is None


def test_temperature_not_a_number(hass: HomeAssistant) -> None:
    """Test that temperature is a number."""
    temp = "Temperature"
    with pytest.raises(Exception) as exception:
        display_temp(hass, temp, UnitOfTemperature.CELSIUS, Precision.HALVES)

    assert f"Temperature is not a number: {temp}" in str(exception.value)


def test_precision_invalid(hass: HomeAssistant) -> None:
    """Test that invalid precision values result in an exception."""
    for precision in [0.2, 0.12345, 0.011]:
        with pytest.raises(Exception) as exception:
            display_temp(hass, TEMP, UnitOfTemperature.CELSIUS, precision)

        expected_message = (
            f"Precision not in [{', '.join(map(str, Precision))}]: {precision}"
        )
        assert expected_message == str(exception.value)


def test_temperature_default_precision(hass: HomeAssistant) -> None:
    """Test default precision when a false value is given."""

    assert display_temp(hass, TEMP, UnitOfTemperature.CELSIUS, 0) == 25
    assert display_temp(hass, TEMP, UnitOfTemperature.CELSIUS, None) == 25


def test_temperature_celsius_celsius(hass: HomeAssistant) -> None:
    """Test temperature celsius to celsius."""

    cases: dict[Precision, float] = {
        Precision.WHOLE: 25,
        Precision.HALVES: 24.5,
        Precision.TENTHS: 24.6,
    }

    for precision in Precision:
        temp = cases[precision]
        assert display_temp(hass, TEMP, UnitOfTemperature.CELSIUS, precision) == temp


def test_temperature_fahrenheit_fahrenheit(hass: HomeAssistant) -> None:
    """Test temperature fahrenheit to fahrenheit."""

    cases: dict[Precision, float] = {
        Precision.WHOLE: 25,
        Precision.HALVES: 24.5,
        Precision.TENTHS: 24.6,
    }

    hass.config.units.temperature_unit = UnitOfTemperature.FAHRENHEIT

    for precision in Precision:
        temp = cases[precision]
        assert display_temp(hass, TEMP, UnitOfTemperature.FAHRENHEIT, precision) == temp

    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS


def test_temperature_fahrenheit_to_celsius(hass: HomeAssistant) -> None:
    """Test temperature fahrenheit to celsius. 24.6366 fahrenheit ~ -4.0908 celsius."""

    cases: dict[Precision, float] = {
        Precision.WHOLE: -4,
        Precision.HALVES: -4,
        Precision.TENTHS: -4.1,
    }

    for precision in Precision:
        temp = cases[precision]
        assert display_temp(hass, TEMP, UnitOfTemperature.FAHRENHEIT, precision) == temp


def test_temperature_celsius_to_fahrenheit(hass: HomeAssistant) -> None:
    """Test temperature celsius to fahrenheit: 24.6366 celsius ~ 76.34588 fahrenheit."""

    cases: dict[Precision, float] = {
        Precision.WHOLE: 76,
        Precision.HALVES: 76.5,
        Precision.TENTHS: 76.3,
    }

    hass.config.units.temperature_unit = UnitOfTemperature.FAHRENHEIT

    for precision in Precision:
        temp = cases[precision]
        assert display_temp(hass, TEMP, UnitOfTemperature.CELSIUS, precision) == temp

    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS
