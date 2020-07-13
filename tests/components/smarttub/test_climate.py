"""Test the SmartTub climate platform."""
from unittest.mock import Mock

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
from homeassistant.components.smarttub.const import DOMAIN, SMARTTUB_CONTROLLER
from homeassistant.components.smarttub.controller import SmartTubController
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.exceptions import PlatformNotReady

from tests.async_mock import create_autospec
from tests.common import MockConfigEntry


@pytest.fixture(name="controller")
async def mock_controller(hass):
    """Mock the controller for testing."""

    controller = create_autospec(SmartTubController, instance=True)
    controller.get_heater_status.return_value = "ON"
    return controller


async def test_async_setup_entry(hass, controller):
    """Test async_setup_entry."""

    entry = MockConfigEntry(unique_id="ceid1")
    async_add_entities = Mock()
    hass.data[DOMAIN] = {
        entry.unique_id: {SMARTTUB_CONTROLLER: controller},
    }
    controller.spa_ids = [1]

    ret = await async_setup_entry(hass, entry, async_add_entities)

    assert ret is True
    async_add_entities.assert_called()

    async_add_entities.reset_mock()
    # simulate not ready
    controller.entity_is_available.return_value = False

    with pytest.raises(PlatformNotReady):
        await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_not_called()


async def test_thermostat(controller):
    """Test the thermostat entity."""

    thermostat = SmartTubThermostat(controller, "spaid1")
    assert thermostat.temperature_unit == TEMP_CELSIUS
    assert thermostat.hvac_action == CURRENT_HVAC_HEAT
    controller.get_heater_status.return_value = "OFF"
    assert thermostat.hvac_action == CURRENT_HVAC_IDLE
    assert thermostat.hvac_modes
    assert thermostat.hvac_mode
    await thermostat.async_set_hvac_mode(HVAC_MODE_HEAT)
    assert thermostat.min_temp
    assert thermostat.max_temp
    assert thermostat.supported_features
    assert thermostat.current_temperature
    assert thermostat.target_temperature
    await thermostat.async_set_temperature(**{ATTR_TEMPERATURE: 30})
    controller.set_target_water_temperature.assert_called_with("spaid1", 30)
