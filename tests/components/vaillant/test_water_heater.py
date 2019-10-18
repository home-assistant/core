"""Tests for the vaillant sensor."""
import datetime

import pytest
from mock import ANY
from pymultimatic.model import System, OperatingModes, QuickModes, HolidayMode, \
    HotWater

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.components.vaillant as vaillant
from homeassistant.components.vaillant import DOMAIN, CONF_WATER_HEATER, \
    ATTR_VAILLANT_MODE
from tests.components.vaillant import SystemManagerMock, _goto_future, _setup, \
    _call_service

VALID_ALL_DISABLED_CONFIG = {
    DOMAIN: {
        CONF_USERNAME: 'test',
        CONF_PASSWORD: 'test',
        CONF_WATER_HEATER: False,
    }
}


def _assert_state(hass, mode, temp, current_temp, away_mode):
    assert len(hass.states.async_entity_ids()) == 1

    assert hass.states.is_state('water_heater.vaillant_hot_water', mode.name)
    state = hass.states.get('water_heater.vaillant_hot_water')
    assert state.attributes['min_temp'] == HotWater.MIN_TARGET_TEMP
    assert state.attributes['max_temp'] == HotWater.MAX_TARGET_TEMP
    assert state.attributes['temperature'] == temp
    assert state.attributes['current_temperature'] == current_temp
    assert state.attributes[ATTR_VAILLANT_MODE] == mode.name

    if mode == QuickModes.HOLIDAY:
        assert state.attributes.get('operation_mode') is None
        assert state.attributes.get('away_mode') is None
        assert state.attributes.get('operation_list') is None
    else:
        assert state.attributes['operation_mode'] == mode.name
        assert state.attributes['away_mode'] == away_mode
        assert set(state.attributes['operation_list']) == {'ON', 'OFF', 'AUTO'}


@pytest.fixture(autouse=True)
def fixture_only_water_heater(mock_system_manager):
    """Mock vaillant to only handle sensor."""
    orig_platforms = vaillant.PLATFORMS
    vaillant.PLATFORMS = ['water_heater']
    yield
    vaillant.PLATFORMS = orig_platforms


async def test_valid_config(hass):
    """Test setup with valid config."""
    assert await _setup(hass)
    _assert_state(hass, OperatingModes.AUTO, HotWater.MIN_TARGET_TEMP, 45,
                  'off')


async def test_valid_config_all_disabled(hass):
    """Test setup with valid config, but water heater disabled."""
    assert await _setup(hass, VALID_ALL_DISABLED_CONFIG)
    assert not hass.states.async_entity_ids()


async def test_empty_system(hass):
    """Test setup with empty system."""
    assert await _setup(hass, system=System(None, None, None, None,
                                            None, None, None, None,
                                            None, None))
    assert not hass.states.async_entity_ids()


async def test_state_update(hass):
    """Test water heater is updated accordingly to data."""
    assert await _setup(hass)
    _assert_state(hass, OperatingModes.AUTO, HotWater.MIN_TARGET_TEMP, 45,
                  'off')

    system = SystemManagerMock.system
    system.hot_water.current_temperature = 65
    system.hot_water.operating_mode = OperatingModes.ON
    system.hot_water.target_temperature = 45
    SystemManagerMock.system = system
    await _goto_future(hass)

    _assert_state(hass, OperatingModes.ON, 45, 65, 'off')


async def test_holiday_mode(hass):
    """Test holiday mode."""
    system = SystemManagerMock.get_default_system()
    system.quick_mode = QuickModes.HOLIDAY
    system.holiday_mode = HolidayMode(True, datetime.date.today(),
                                      datetime.date.today(), 15)

    assert await _setup(hass, system=system)
    _assert_state(hass, QuickModes.HOLIDAY, HotWater.MIN_TARGET_TEMP, 45, 'on')


async def test_away_mode(hass):
    """Test away mode."""
    system = SystemManagerMock.get_default_system()
    system.hot_water.operating_mode = OperatingModes.OFF

    assert await _setup(hass, system=system)
    _assert_state(hass, OperatingModes.OFF, HotWater.MIN_TARGET_TEMP, 45, 'on')


async def test_water_boost(hass):
    """Test hot water boost mode."""
    system = SystemManagerMock.get_default_system()
    system.quick_mode = QuickModes.HOTWATER_BOOST

    assert await _setup(hass, system=system)
    _assert_state(hass, QuickModes.HOTWATER_BOOST, 40, 45, 'off')


async def test_system_off(hass):
    """Test system off mode."""
    system = SystemManagerMock.get_default_system()
    system.quick_mode = QuickModes.SYSTEM_OFF

    assert await _setup(hass, system=system)
    _assert_state(hass, QuickModes.SYSTEM_OFF, HotWater.MIN_TARGET_TEMP, 45,
                  'on')


async def test_one_day_away(hass):
    """Test one day away mode."""
    system = SystemManagerMock.get_default_system()
    system.quick_mode = QuickModes.ONE_DAY_AWAY

    assert await _setup(hass, system=system)
    _assert_state(hass, QuickModes.ONE_DAY_AWAY, HotWater.MIN_TARGET_TEMP, 45,
                  'on')


async def test_turn_away_mode_on(hass):
    """Test turn away mode on."""
    assert await _setup(hass)

    hot_water = SystemManagerMock.system.hot_water
    hot_water.operating_mode = OperatingModes.OFF
    SystemManagerMock.instance.get_hot_water.return_value = hot_water

    await hass.services.async_call('water_heater',
                                   'set_away_mode',
                                   {
                                       'entity_id':
                                           'water_heater.vaillant_hot_water',
                                       'away_mode': True
                                   })
    await hass.async_block_till_done()

    SystemManagerMock.instance.set_hot_water_operating_mode. \
        assert_called_once_with(ANY, OperatingModes.OFF)
    _assert_state(hass, OperatingModes.OFF, HotWater.MIN_TARGET_TEMP, 45, 'on')


async def test_turn_away_mode_off(hass):
    """Test turn away mode off."""
    assert await _setup(hass)

    hot_water = SystemManagerMock.system.hot_water
    hot_water.operating_mode = OperatingModes.AUTO
    SystemManagerMock.instance.get_hot_water.return_value = hot_water

    await hass.services.async_call('water_heater',
                                   'set_away_mode',
                                   {
                                       'entity_id':
                                           'water_heater.vaillant_hot_water',
                                       'away_mode': False
                                   })
    await hass.async_block_till_done()

    SystemManagerMock.instance.set_hot_water_operating_mode. \
        assert_called_once_with(ANY, OperatingModes.AUTO)

    _assert_state(hass, OperatingModes.AUTO, HotWater.MIN_TARGET_TEMP, 45,
                  'off')


async def test_set_operating_mode(hass):
    """Test set operation mode."""
    assert await _setup(hass)

    hot_water = SystemManagerMock.system.hot_water
    hot_water.operating_mode = OperatingModes.ON
    SystemManagerMock.instance.get_hot_water.return_value = hot_water

    await hass.services.async_call('water_heater',
                                   'set_operation_mode',
                                   {
                                       'entity_id':
                                           'water_heater.vaillant_hot_water',
                                       'operation_mode': 'ON'
                                   })
    await hass.async_block_till_done()

    SystemManagerMock.instance.set_hot_water_operating_mode \
        .assert_called_once_with(ANY, OperatingModes.ON)
    _assert_state(hass, OperatingModes.ON, 40, 45, 'off')


async def test_set_operating_mode_wrong(hass):
    """Test set operation mode with wrong mode."""
    assert await _setup(hass)

    await hass.services.async_call('water_heater',
                                   'set_operation_mode',
                                   {
                                       'entity_id':
                                           'water_heater.vaillant_hot_water',
                                       'operation_mode': 'wrong'
                                   })
    await hass.async_block_till_done()

    SystemManagerMock.instance.set_hot_water_operating_mode \
        .assert_not_called()
    _assert_state(hass, OperatingModes.AUTO, HotWater.MIN_TARGET_TEMP, 45,
                  'off')


async def test_set_temperature(hass):
    """Test set target temperature."""
    system = SystemManagerMock.get_default_system()
    system.hot_water.operating_mode = OperatingModes.AUTO
    assert await _setup(hass, system=system)

    SystemManagerMock.instance.get_hot_water.return_value = \
        SystemManagerMock.system.hot_water

    await _call_service(hass, 'water_heater', 'set_temperature',
                        {
                            'entity_id': 'water_heater.vaillant_hot_water',
                            'temperature': 50
                        })

    SystemManagerMock.instance.set_hot_water_setpoint_temperature \
        .assert_called_once_with('hot_water', 50)
    SystemManagerMock.instance.set_hot_water_operating_mode \
        .assert_called_once_with('hot_water', OperatingModes.ON)


async def test_set_temperature_already_on(hass):
    """Test set target temperature."""
    system = SystemManagerMock.get_default_system()
    system.hot_water.operating_mode = OperatingModes.ON
    assert await _setup(hass, system=system)

    SystemManagerMock.instance.get_hot_water.return_value = \
        SystemManagerMock.system.hot_water

    await _call_service(hass, 'water_heater', 'set_temperature',
                        {
                            'entity_id': 'water_heater.vaillant_hot_water',
                            'temperature': 50
                        })

    SystemManagerMock.instance.set_hot_water_setpoint_temperature \
        .assert_called_once_with('hot_water', 50)
    SystemManagerMock.instance.set_hot_water_operating_mode.assert_not_called()


async def test_set_operating_mode_while_quick_mode(hass):
    system = SystemManagerMock.get_default_system()
    system.quick_mode = QuickModes.PARTY
    assert await _setup(hass, system=system)

    await _call_service(hass, 'water_heater', 'set_operation_mode',
                        {
                            'entity_id': 'water_heater.vaillant_hot_water',
                            'operation_mode': 'AUTO'
                        })
    SystemManagerMock.instance.set_hot_water_operating_mode\
        .assert_called_once_with('hot_water', OperatingModes.AUTO)
    SystemManagerMock.instance.remove_quick_mode.assert_not_called()


async def test_set_operating_mode_while_quick_mode_for_dhw(hass):
    system = SystemManagerMock.get_default_system()
    system.quick_mode = QuickModes.HOTWATER_BOOST
    assert await _setup(hass, system=system)

    await _call_service(hass, 'water_heater', 'set_operation_mode',
                        {
                            'entity_id': 'water_heater.vaillant_hot_water',
                            'operation_mode': 'AUTO'
                        })
    SystemManagerMock.instance.set_hot_water_operating_mode\
        .assert_called_once_with('hot_water', OperatingModes.AUTO)
    SystemManagerMock.instance.remove_quick_mode.assert_called_once_with()
