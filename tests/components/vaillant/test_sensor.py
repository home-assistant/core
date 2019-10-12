"""Tests for the vaillant sensor."""

import pytest
from pymultimatic.model import System

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.components.vaillant as vaillant
from homeassistant.components.vaillant import DOMAIN, \
    CONF_SENSOR_BOILER_WATER_TEMPERATURE, CONF_SENSOR_BOILER_WATER_PRESSURE, \
    CONF_SENSOR_ROOM_TEMPERATURE, CONF_SENSOR_ZONE_TEMPERATURE, \
    CONF_SENSOR_OUTDOOR_TEMPERATURE, CONF_SENSOR_HOT_WATER_TEMPERATURE
from tests.components.vaillant import SystemManagerMock, _goto_future, _setup

VALID_ALL_DISABLED_CONFIG = {
    DOMAIN: {
        CONF_USERNAME: 'test',
        CONF_PASSWORD: 'test',
        CONF_SENSOR_BOILER_WATER_TEMPERATURE: False,
        CONF_SENSOR_BOILER_WATER_PRESSURE: False,
        CONF_SENSOR_ROOM_TEMPERATURE: False,
        CONF_SENSOR_ZONE_TEMPERATURE: False,
        CONF_SENSOR_OUTDOOR_TEMPERATURE: False,
        CONF_SENSOR_HOT_WATER_TEMPERATURE: False,
    }
}


@pytest.fixture(autouse=True)
def fixture_only_sensor(mock_system_manager):
    """Mock vaillant to only handle sensor."""
    orig_platforms = vaillant.PLATFORMS
    vaillant.PLATFORMS = ['sensor']
    yield
    vaillant.PLATFORMS = orig_platforms


async def test_valid_config(hass):
    """Test setup with valid config."""
    assert await _setup(hass)
    assert len(hass.states.async_entity_ids()) == 6


async def test_valid_config_all_disabled(hass):
    """Test setup with valid config, but all senors disabled."""
    assert await _setup(hass, VALID_ALL_DISABLED_CONFIG)
    assert not hass.states.async_entity_ids()


async def test_empty_system(hass):
    """Test setup with empty system."""
    assert await _setup(hass, system=System(None, None, None, None,
                                            None, None, None, None,
                                            None, None))
    assert not hass.states.async_entity_ids()


async def test_state_update(hass):
    """Test all sensors are updated accordingly to data."""
    assert await _setup(hass)
    assert len(hass.states.async_entity_ids()) == 6

    assert hass.states.is_state('sensor.vaillant_boiler_pressure', '1.4')
    assert hass.states.is_state('sensor.vaillant_boiler_temperature', '20')
    assert hass.states.is_state('sensor.vaillant_room_1_temperature', '22')
    assert hass.states.is_state('sensor.vaillant_hot_water_temperature', '45')
    assert hass.states.is_state('sensor.vaillant_outdoor_temperature', '18')
    assert hass.states.is_state('sensor.vaillant_zone_1_temperature', '25')

    system = SystemManagerMock.system
    system.outdoor_temperature = 21
    system.rooms[0].current_temperature = 30
    system.zones[0].current_temperature = 31
    system.boiler_status.water_pressure = 1.6
    system.boiler_status.current_temperature = 32
    system.hot_water.current_temperature = 66
    SystemManagerMock.system = system

    await _goto_future(hass)

    assert hass.states.is_state('sensor.vaillant_boiler_pressure', '1.6')
    assert hass.states.is_state('sensor.vaillant_boiler_temperature', '32')
    assert hass.states.is_state('sensor.vaillant_room_1_temperature', '30')
    assert hass.states.is_state('sensor.vaillant_hot_water_temperature', '66')
    assert hass.states.is_state('sensor.vaillant_outdoor_temperature', '21')
    assert hass.states.is_state('sensor.vaillant_zone_1_temperature', '31')
