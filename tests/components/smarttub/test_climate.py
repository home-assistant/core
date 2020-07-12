"""Test the SmartTub climate platform."""

import pytest

from homeassistant.components.climate.const import HVAC_MODE_HEAT
from homeassistant.components.smarttub.climate import SmartTubThermostat
from homeassistant.components.smarttub.controller import SmartTubController
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from tests.async_mock import create_autospec


@pytest.fixture(name="controller")
async def mock_controller(hass):
    """Mock the controller for testing."""

    controller = create_autospec(SmartTubController, instance=True)
    controller.get_heater_status.return_value = "ON"
    return controller


async def test_thermostat(controller):
    """Test the thermostat entity."""

    thermostat = SmartTubThermostat(controller, "spaid1")
    assert thermostat.temperature_unit == TEMP_CELSIUS
    assert thermostat.hvac_action
    assert thermostat.hvac_modes
    assert thermostat.hvac_mode
    await thermostat.async_set_hvac_mode(HVAC_MODE_HEAT)
    assert thermostat.min_temp
    assert thermostat.max_temp
    assert thermostat.supported_features
    assert thermostat.target_temperature
    await thermostat.async_set_temperature(**{ATTR_TEMPERATURE: 30})
    controller.set_target_water_temperature.assert_called_with("spaid1", 30)
