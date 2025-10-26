"""Test helper functions for Saunum Leil Sauna Control Unit integration."""

from homeassistant.components.saunum.helpers import (
    convert_temperature,
    get_temperature_range_for_unit,
    get_temperature_unit,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant


async def test_convert_temperature_none(hass: HomeAssistant) -> None:
    """Test convert_temperature with None value."""
    result = convert_temperature(
        None, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
    )
    assert result is None


async def test_convert_temperature_same_unit(hass: HomeAssistant) -> None:
    """Test convert_temperature when from_unit equals to_unit (short-circuit)."""
    # This tests the missing line 23: from_unit == to_unit case
    result = convert_temperature(
        80.0, UnitOfTemperature.CELSIUS, UnitOfTemperature.CELSIUS
    )
    assert result == 80.0

    result = convert_temperature(
        176.0, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.FAHRENHEIT
    )
    assert result == 176.0


async def test_convert_temperature_celsius_to_fahrenheit(hass: HomeAssistant) -> None:
    """Test convert_temperature from Celsius to Fahrenheit."""
    result = convert_temperature(
        80.0, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
    )
    assert result == 176.0


async def test_convert_temperature_fahrenheit_to_celsius(hass: HomeAssistant) -> None:
    """Test convert_temperature from Fahrenheit to Celsius."""
    result = convert_temperature(
        176.0, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
    )
    assert result == 80.0


async def test_get_temperature_range_celsius(hass: HomeAssistant) -> None:
    """Test get_temperature_range_for_unit for Celsius."""
    min_temp, max_temp = get_temperature_range_for_unit(UnitOfTemperature.CELSIUS)
    assert min_temp == 40
    assert max_temp == 100


async def test_get_temperature_range_fahrenheit(hass: HomeAssistant) -> None:
    """Test get_temperature_range_for_unit for Fahrenheit."""
    min_temp, max_temp = get_temperature_range_for_unit(UnitOfTemperature.FAHRENHEIT)
    assert min_temp == 104
    assert max_temp == 212


async def test_get_temperature_unit(hass: HomeAssistant) -> None:
    """Test get_temperature_unit returns Home Assistant config unit."""
    unit = get_temperature_unit(hass)
    # Default should be Celsius (metric)
    assert unit == UnitOfTemperature.CELSIUS
