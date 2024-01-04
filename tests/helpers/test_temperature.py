"""Tests Home Assistant temperature helpers."""
import pytest

from homeassistant.const import Precision, RoundMode, UnitOfTemperature
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


def test_round_mode_invalid(hass: HomeAssistant) -> None:
    """Test that invalid round_mode values result in an exception."""
    for round_mode in ["Nearest", "flooR", "Foo"]:
        with pytest.raises(Exception) as exception:
            display_temp(hass, TEMP, UnitOfTemperature.CELSIUS, 1, round_mode)

        expected_message = (
            f"RoundMode not in [{', '.join(map(str, RoundMode))}]: {round_mode}"
        )
        assert expected_message == str(exception.value)


def test_temperature_default_precision(hass: HomeAssistant) -> None:
    """Test default precision when a false value is given."""

    assert display_temp(hass, TEMP, UnitOfTemperature.CELSIUS, 0) == 25
    assert display_temp(hass, TEMP, UnitOfTemperature.CELSIUS, None) == 25


def test_temperature_celsius_celsius(hass: HomeAssistant) -> None:
    """Test temperature celsius to celsius."""

    cases: dict[(Precision, RoundMode), float] = {
        (Precision.WHOLE, RoundMode.NEAREST): 25,
        (Precision.WHOLE, RoundMode.DOWN): 24,
        (Precision.WHOLE, RoundMode.UP): 25,
        (Precision.HALVES, RoundMode.NEAREST): 24.5,
        (Precision.HALVES, RoundMode.DOWN): 24.5,
        (Precision.HALVES, RoundMode.UP): 25.0,
        (Precision.TENTHS, RoundMode.NEAREST): 24.6,
        (Precision.TENTHS, RoundMode.DOWN): 24.6,
        (Precision.TENTHS, RoundMode.UP): 24.7,
    }

    for precision in Precision:
        for round_mode in RoundMode:
            temp = cases[(precision, round_mode)]
            assert (
                display_temp(
                    hass, TEMP, UnitOfTemperature.CELSIUS, precision, round_mode
                )
                == temp
            )


def test_temperature_fahrenheit_fahrenheit(hass: HomeAssistant) -> None:
    """Test temperature fahrenheit to fahrenheit."""

    cases: dict[(Precision, RoundMode), float] = {
        (Precision.WHOLE, RoundMode.NEAREST): 25,
        (Precision.WHOLE, RoundMode.DOWN): 24,
        (Precision.WHOLE, RoundMode.UP): 25,
        (Precision.HALVES, RoundMode.NEAREST): 24.5,
        (Precision.HALVES, RoundMode.DOWN): 24.5,
        (Precision.HALVES, RoundMode.UP): 25.0,
        (Precision.TENTHS, RoundMode.NEAREST): 24.6,
        (Precision.TENTHS, RoundMode.DOWN): 24.6,
        (Precision.TENTHS, RoundMode.UP): 24.7,
    }

    hass.config.units.temperature_unit = UnitOfTemperature.FAHRENHEIT

    for precision in Precision:
        for round_mode in RoundMode:
            temp = cases[(precision, round_mode)]
            assert (
                display_temp(
                    hass, TEMP, UnitOfTemperature.FAHRENHEIT, precision, round_mode
                )
                == temp
            )

    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS


def test_temperature_fahrenheit_to_celsius(hass: HomeAssistant) -> None:
    """Test temperature fahrenheit to celsius. 24.6366 fahrenheit ~ -4.0908 celsius."""

    cases: dict[(Precision, RoundMode), float] = {
        (Precision.WHOLE, RoundMode.NEAREST): -4,
        (Precision.WHOLE, RoundMode.DOWN): -5,
        (Precision.WHOLE, RoundMode.UP): -4,
        (Precision.HALVES, RoundMode.NEAREST): -4,
        (Precision.HALVES, RoundMode.DOWN): -4.5,
        (Precision.HALVES, RoundMode.UP): -4,
        (Precision.TENTHS, RoundMode.NEAREST): -4.1,
        (Precision.TENTHS, RoundMode.DOWN): -4.1,
        (Precision.TENTHS, RoundMode.UP): -4,
    }

    for precision in Precision:
        for round_mode in RoundMode:
            temp = cases[(precision, round_mode)]
            assert (
                display_temp(
                    hass, TEMP, UnitOfTemperature.FAHRENHEIT, precision, round_mode
                )
                == temp
            )


def test_temperature_celsius_to_fahrenheit(hass: HomeAssistant) -> None:
    """Test temperature celsius to fahrenheit: 24.6366 celsius ~ 76.34588 fahrenheit."""

    cases: dict[(Precision, RoundMode), float] = {
        (Precision.WHOLE, RoundMode.NEAREST): 76,
        (Precision.WHOLE, RoundMode.DOWN): 76,
        (Precision.WHOLE, RoundMode.UP): 77,
        (Precision.HALVES, RoundMode.NEAREST): 76.5,
        (Precision.HALVES, RoundMode.DOWN): 76,
        (Precision.HALVES, RoundMode.UP): 76.5,
        (Precision.TENTHS, RoundMode.NEAREST): 76.3,
        (Precision.TENTHS, RoundMode.DOWN): 76.3,
        (Precision.TENTHS, RoundMode.UP): 76.4,
    }

    hass.config.units.temperature_unit = UnitOfTemperature.FAHRENHEIT

    for precision in Precision:
        for round_mode in RoundMode:
            temp = cases[(precision, round_mode)]
            assert (
                display_temp(
                    hass, TEMP, UnitOfTemperature.CELSIUS, precision, round_mode
                )
                == temp
            )

    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS
