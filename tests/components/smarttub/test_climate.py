"""Test the SmartTub climate platform."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_HEAT,
)
from homeassistant.components.smarttub.climate import (
    SmartTubThermostat,
    async_setup_entry,
)
from homeassistant.components.smarttub.const import (
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN,
    SMARTTUB_CONTROLLER,
)
from homeassistant.components.smarttub.controller import SmartTubController
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from tests.async_mock import create_autospec
from tests.common import MockConfigEntry


@pytest.fixture(name="controller")
async def mock_controller(hass, coordinator):
    """Mock the controller for testing."""

    controller = create_autospec(SmartTubController, instance=True)
    controller.coordinator = coordinator
    return controller


async def test_async_setup_entry(hass, controller, spa):
    """Test async_setup_entry."""

    entry = MockConfigEntry(unique_id="ceid1")
    async_add_entities = Mock()
    hass.data[DOMAIN] = {
        entry.unique_id: {SMARTTUB_CONTROLLER: controller},
    }
    controller.spas = [spa]

    ret = await async_setup_entry(hass, entry, async_add_entities)

    assert ret is True
    async_add_entities.assert_called()


async def test_thermostat(coordinator, spa):
    """Test the thermostat entity."""

    coordinator.data = {
        spa.id: {
            "status": {
                "heater": "ON",
                "water": {
                    "temperature": 38,
                },
                "setTemperature": 39,
            }
        }
    }
    thermostat = SmartTubThermostat(coordinator, spa)
    assert thermostat.temperature_unit == TEMP_CELSIUS
    assert thermostat.hvac_action == CURRENT_HVAC_HEAT
    coordinator.data[spa.id]["status"]["heater"] = "OFF"
    assert thermostat.hvac_action == CURRENT_HVAC_IDLE
    assert thermostat.hvac_modes
    assert thermostat.hvac_mode
    await thermostat.async_set_hvac_mode(HVAC_MODE_HEAT)
    assert thermostat.min_temp == DEFAULT_MIN_TEMP
    assert thermostat.max_temp == DEFAULT_MAX_TEMP
    assert thermostat.supported_features
    assert thermostat.current_temperature == 38
    assert thermostat.target_temperature == 39

    with patch.object(thermostat, "async_schedule_update_ha_state") as mock:
        await thermostat.async_set_temperature(**{ATTR_TEMPERATURE: 30})
        spa.set_temperature.assert_called_with(30)
        mock.assert_called_with(True)
