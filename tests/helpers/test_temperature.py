"""Tests Home Assistant temperature helpers."""

import pytest

from homeassistant.const import (
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.temperature import display_temp, display_temp_interval
from homeassistant.util.unit_system import (
    _CONF_UNIT_SYSTEM_METRIC,
    _CONF_UNIT_SYSTEM_US_CUSTOMARY,
)

TEMP = 24.636626
TEMP_INTERVAL = 0.5


def test_temperature_not_a_number(hass: HomeAssistant) -> None:
    """Test that temperature is a number."""
    temp = "Temperature"
    with pytest.raises(Exception) as exception:
        display_temp(hass, temp, UnitOfTemperature.CELSIUS, PRECISION_HALVES)

    assert f"Temperature is not a number: {temp}" in str(exception.value)


def test_celsius_halves(hass: HomeAssistant) -> None:
    """Test temperature to celsius rounding to halves."""
    assert display_temp(hass, TEMP, UnitOfTemperature.CELSIUS, PRECISION_HALVES) == 24.5


def test_celsius_tenths(hass: HomeAssistant) -> None:
    """Test temperature to celsius rounding to tenths."""
    assert display_temp(hass, TEMP, UnitOfTemperature.CELSIUS, PRECISION_TENTHS) == 24.6


def test_fahrenheit_wholes(hass: HomeAssistant) -> None:
    """Test temperature to fahrenheit rounding to wholes."""
    assert display_temp(hass, TEMP, UnitOfTemperature.FAHRENHEIT, PRECISION_WHOLE) == -4


def test_temperature_interval_not_a_number(hass: HomeAssistant) -> None:
    """Test that temperature is a number."""
    temp = "Temperature"
    with pytest.raises(TypeError) as exception:
        display_temp_interval(hass, temp, UnitOfTemperature.CELSIUS, PRECISION_HALVES)

    assert f"Temperature interval is not a number: {temp}" in str(exception.value)


@pytest.mark.parametrize(
    ("unit_system", "unit", "results"),
    [
        (
            _CONF_UNIT_SYSTEM_METRIC,
            UnitOfTemperature.CELSIUS,
            {
                PRECISION_HALVES: 0.5,
                PRECISION_TENTHS: 0.5,
                PRECISION_WHOLE: 1,
            },
        ),
        (
            _CONF_UNIT_SYSTEM_US_CUSTOMARY,
            UnitOfTemperature.CELSIUS,
            {
                PRECISION_HALVES: 1,
                PRECISION_TENTHS: 0.9,
                PRECISION_WHOLE: 1,
            },
        ),
        (
            _CONF_UNIT_SYSTEM_METRIC,
            UnitOfTemperature.FAHRENHEIT,
            {
                PRECISION_HALVES: 0.5,
                PRECISION_TENTHS: 0.3,
                PRECISION_WHOLE: 0,
            },
        ),
        (
            _CONF_UNIT_SYSTEM_US_CUSTOMARY,
            UnitOfTemperature.FAHRENHEIT,
            {
                PRECISION_HALVES: 0.5,
                PRECISION_TENTHS: 0.5,
                PRECISION_WHOLE: 1,
            },
        ),
    ],
)
async def test_temperature_interval(
    hass: HomeAssistant, unit_system: str, unit: UnitOfTemperature, results: dict
) -> None:
    """Test temperature interval rendering with different system units and precisions."""

    _old_unit_system = hass.config.units
    if _old_unit_system._name != unit_system:
        await hass.config.async_update(unit_system=unit_system)

    try:
        for precision, result in results.items():
            assert (
                display_temp_interval(hass, TEMP_INTERVAL, unit, precision) == result
            ), f"unit: {unit} precision:{precision} expected:{result}"

    finally:
        if _old_unit_system._name != unit_system:
            await hass.config.async_update(unit_system=_old_unit_system._name)
