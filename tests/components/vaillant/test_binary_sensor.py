"""Tests for the vaillant sensor."""

import pytest
from pymultimatic.model import OperatingModes, Room, Device, Circulation,\
    System, SettingModes

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.components.vaillant as vaillant
from homeassistant.components.vaillant import DOMAIN, \
    CONF_BINARY_SENSOR_BOILER_ERROR, CONF_BINARY_SENSOR_DEVICE_BATTERY, \
    CONF_BINARY_SENSOR_CIRCULATION, CONF_BINARY_SENSOR_DEVICE_RADIO_REACH, \
    CONF_BINARY_SENSOR_ROOM_WINDOW, CONF_BINARY_SENSOR_SYSTEM_ONLINE, \
    CONF_BINARY_SENSOR_ROOM_CHILD_LOCK, CONF_BINARY_SENSOR_SYSTEM_UPDATE
from tests.components.vaillant import SystemManagerMock, _goto_future, _setup

VALID_ALL_DISABLED_CONFIG = {
    DOMAIN: {
        CONF_USERNAME: 'test',
        CONF_PASSWORD: 'test',
        CONF_BINARY_SENSOR_BOILER_ERROR: False,
        CONF_BINARY_SENSOR_DEVICE_BATTERY: False,
        CONF_BINARY_SENSOR_CIRCULATION: False,
        CONF_BINARY_SENSOR_DEVICE_RADIO_REACH: False,
        CONF_BINARY_SENSOR_ROOM_WINDOW: False,
        CONF_BINARY_SENSOR_SYSTEM_ONLINE: False,
        CONF_BINARY_SENSOR_ROOM_CHILD_LOCK: False,
        CONF_BINARY_SENSOR_SYSTEM_UPDATE: False
    }
}


@pytest.fixture(autouse=True)
def fixture_only_binary_sensor(mock_system_manager):
    """Mock vaillant to only handle binary_sensor."""
    orig_platforms = vaillant.PLATFORMS
    vaillant.PLATFORMS = ['binary_sensor']
    yield
    vaillant.PLATFORMS = orig_platforms


async def test_valid_config(hass):
    """Test setup with valid config."""
    assert await _setup(hass)
    assert len(hass.states.async_entity_ids()) == 8


async def test_valid_config_all_disabled(hass):
    """Test setup with valid config, but all binary_senors disabled."""
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
    assert len(hass.states.async_entity_ids()) == 8

    assert hass.states.is_state(
        'binary_sensor.vaillant_circulation_power', 'off')
    assert hass.states.is_state('binary_sensor.vaillant_room_1_window', 'off')
    assert hass.states.is_state('binary_sensor.vaillant_room_1_lock', 'on')
    assert hass.states.is_state(
        'binary_sensor.vaillant_123456789_battery', 'off')
    assert hass.states.is_state('binary_sensor.vaillant_boiler_problem', 'off')
    assert hass.states.is_state(
        'binary_sensor.vaillant_123456789_connectivity', 'on')
    assert hass.states.is_state(
        'binary_sensor.vaillant_system_power', 'off')
    assert hass.states.is_state(
        'binary_sensor.vaillant_system_connectivity', 'on')

    system = SystemManagerMock.system
    system.circulation = Circulation(
        'circulation', 'Circulation',
        SystemManagerMock.time_program(SettingModes.ON), OperatingModes.AUTO)

    room_device = Device('Device 1', '123456789', 'VALVE', True, True)
    system.set_room('1', Room('1', 'Room 1', SystemManagerMock.time_program(),
                              22, 24, OperatingModes.AUTO, None, True, True,
                              [room_device]))

    system.boiler_status.status_code = 'F11'
    system.system_status.online_status = 'OFFLINE'
    system.system_status.update_status = 'UPDATE_PENDING'
    SystemManagerMock.system = system

    await _goto_future(hass)

    assert len(hass.states.async_entity_ids()) == 8
    assert hass.states.is_state(
        'binary_sensor.vaillant_circulation_power', 'on')
    assert hass.states.is_state('binary_sensor.vaillant_room_1_window', 'on')
    assert hass.states.is_state('binary_sensor.vaillant_room_1_lock', 'off')
    assert hass.states.is_state(
        'binary_sensor.vaillant_123456789_battery', 'on')
    assert hass.states.is_state('binary_sensor.vaillant_boiler_problem', 'on')
    assert hass.states.is_state(
        'binary_sensor.vaillant_123456789_connectivity', 'off')
    assert hass.states.is_state(
        'binary_sensor.vaillant_system_power', 'on')
    assert hass.states.is_state(
        'binary_sensor.vaillant_system_connectivity', 'off')
