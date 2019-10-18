"""Tests for the vaillant sensor."""
import pytest
from datetime import datetime, timedelta
from pymultimatic.model import OperatingModes, Room, Device, Circulation, \
    System, SettingModes, HolidayMode

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.components.vaillant as vaillant
from homeassistant.components.vaillant import DOMAIN, \
    CONF_BINARY_SENSOR_BOILER_ERROR, CONF_BINARY_SENSOR_DEVICE_BATTERY, \
    CONF_BINARY_SENSOR_CIRCULATION, CONF_BINARY_SENSOR_DEVICE_RADIO_REACH, \
    CONF_BINARY_SENSOR_ROOM_WINDOW, CONF_BINARY_SENSOR_SYSTEM_ONLINE, \
    CONF_BINARY_SENSOR_ROOM_CHILD_LOCK, CONF_BINARY_SENSOR_SYSTEM_UPDATE,\
    CONF_BINARY_SENSOR_HOLIDAY_MODE, CONF_BINARY_SENSOR_QUICK_MODE
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
        CONF_BINARY_SENSOR_SYSTEM_UPDATE: False,
        CONF_BINARY_SENSOR_HOLIDAY_MODE: False,
        CONF_BINARY_SENSOR_QUICK_MODE: False
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
    assert len(hass.states.async_entity_ids()) == 10


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
    assert len(hass.states.async_entity_ids()) == 10

    assert hass.states.is_state(
        'binary_sensor.vaillant_circulation', 'off')
    assert hass.states.is_state('binary_sensor.vaillant_room_1_window', 'off')
    assert hass.states.is_state('binary_sensor.vaillant_room_1_lock', 'on')
    assert hass.states.is_state(
        'binary_sensor.vaillant_123456789_battery', 'off')
    assert hass.states.is_state('binary_sensor.vaillant_boiler', 'off')
    assert hass.states.is_state(
        'binary_sensor.vaillant_123456789_connectivity', 'on')
    assert hass.states.is_state(
        'binary_sensor.vaillant_system_update', 'off')
    assert hass.states.is_state(
        'binary_sensor.vaillant_system_online', 'on')
    assert hass.states.is_state(
        'binary_sensor.vaillant_holiday', 'off')
    state = hass.states.get('binary_sensor.vaillant_holiday')
    assert state.attributes.get('start_date') is None
    assert state.attributes.get('end_date') is None
    assert state.attributes.get('temperature') is None
    assert hass.states.is_state(
        'binary_sensor.vaillant_quick_mode', 'off')

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
    system.holiday_mode = \
        HolidayMode(True,
                    datetime.now().date() - timedelta(days=1),
                    datetime.now().date() + timedelta(days=1))
    SystemManagerMock.system = system

    await _goto_future(hass)

    assert len(hass.states.async_entity_ids()) == 10
    assert hass.states.is_state(
        'binary_sensor.vaillant_circulation', 'on')
    assert hass.states.is_state('binary_sensor.vaillant_room_1_window', 'on')
    assert hass.states.is_state('binary_sensor.vaillant_room_1_lock', 'off')
    assert hass.states.is_state(
        'binary_sensor.vaillant_123456789_battery', 'on')
    assert hass.states.is_state('binary_sensor.vaillant_boiler', 'on')
    assert hass.states.is_state(
        'binary_sensor.vaillant_123456789_connectivity', 'off')
    assert hass.states.is_state(
        'binary_sensor.vaillant_system_update', 'on')
    assert hass.states.is_state(
        'binary_sensor.vaillant_system_online', 'off')
    assert hass.states.is_state(
        'binary_sensor.vaillant_holiday', 'on')
    state = hass.states.get('binary_sensor.vaillant_holiday')
    assert state.attributes['start_date'] == \
        system.holiday_mode.start_date.isoformat()
    assert state.attributes['end_date'] ==\
        system.holiday_mode.end_date.isoformat()
    assert state.attributes['temperature'] == \
        system.holiday_mode.target_temperature
    assert hass.states.is_state(
        'binary_sensor.vaillant_quick_mode', 'off')
