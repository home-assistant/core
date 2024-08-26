"""Tests for the BSB-Lan climate platform."""

from bsblan import BSBLANError
import pytest

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    PRESET_ECO,
    PRESET_NONE,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError


async def test_climate_init(climate) -> None:
    """Test initialization of the climate entity."""
    assert climate.unique_id == "00:80:41:19:69:90-climate"
    assert climate.temperature_unit == UnitOfTemperature.CELSIUS
    assert climate.min_temp == 8.0
    assert climate.max_temp == 20.0


def test_temperature_unit_assignment(climate_fahrenheit) -> None:
    """Test the temperature unit assignment based on the static data."""
    assert climate_fahrenheit._attr_temperature_unit == UnitOfTemperature.FAHRENHEIT


async def test_climate_properties(climate, mock_bsblan) -> None:
    """Test properties of the climate entity."""
    assert climate.current_temperature == 18.6
    assert climate.target_temperature == 18.5
    assert climate.hvac_mode == HVACMode.HEAT
    assert climate.preset_mode == PRESET_NONE

    mock_bsblan.state.return_value.current_temperature.value = "---"
    assert climate.current_temperature is None

    mock_bsblan.state.return_value.hvac_mode.value = PRESET_ECO
    assert climate.preset_mode == PRESET_ECO
    assert climate.hvac_mode == HVACMode.AUTO


async def test_climate_set_hvac_mode(climate, mock_bsblan) -> None:
    """Test setting the HVAC mode."""
    await climate.async_set_hvac_mode(HVACMode.HEAT)
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=HVACMode.HEAT)


async def test_climate_set_preset_mode(climate, mock_bsblan) -> None:
    """Test setting the preset mode."""
    mock_bsblan.state.return_value.hvac_mode.value = HVACMode.AUTO
    await climate.async_set_preset_mode(PRESET_NONE)
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=HVACMode.AUTO)


async def test_climate_set_temperature(climate, mock_bsblan) -> None:
    """Test setting the target temperature."""
    await climate.async_set_temperature(**{ATTR_TEMPERATURE: 20})
    mock_bsblan.thermostat.assert_called_once_with(target_temperature=20)


async def test_climate_set_data_error(climate, mock_bsblan) -> None:
    """Test error while setting data."""
    mock_bsblan.thermostat.side_effect = BSBLANError
    with pytest.raises(HomeAssistantError):
        await climate.async_set_temperature(**{ATTR_TEMPERATURE: 20})


async def test_climate_current_temperature_none(climate, mock_bsblan) -> None:
    """Test when the current temperature value is '---'."""
    mock_bsblan.state.return_value.current_temperature.value = "---"
    assert climate.current_temperature is None


async def test_climate_turn_on(climate, mock_bsblan) -> None:
    """Test turning on the climate entity."""
    await climate.async_turn_on()
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=HVACMode.HEAT)


async def test_climate_turn_off(climate, mock_bsblan) -> None:
    """Test turning off the climate entity."""
    await climate.async_turn_off()
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=HVACMode.OFF)


async def test_climate_set_preset_mode_eco(climate, mock_bsblan) -> None:
    """Test setting the preset mode to eco."""
    mock_bsblan.state.return_value.hvac_mode.value = HVACMode.AUTO
    await climate.async_set_preset_mode(PRESET_ECO)
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=PRESET_ECO)
    assert climate.hvac_mode == HVACMode.AUTO


async def test_climate_set_preset_mode_error(climate, mock_bsblan) -> None:
    """Test setting the preset mode when it fails with a BSBLANError."""
    mock_bsblan.thermostat.side_effect = BSBLANError
    with pytest.raises(HomeAssistantError):
        await climate.async_set_preset_mode(PRESET_ECO)
