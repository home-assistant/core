"""Tests for the vaillant sensor."""
import datetime

import pytest
from pymultimatic.model import System, OperatingModes, QuickModes, \
    HolidayMode, Room, Zone, SettingModes, QuickVeto

from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    SUPPORT_TARGET_TEMPERATURE_RANGE, SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.components.vaillant as vaillant
from homeassistant.components.vaillant import DOMAIN, CONF_ROOM_CLIMATE, \
    CONF_ZONE_CLIMATE, ATTR_VAILLANT_MODE
from tests.components.vaillant import SystemManagerMock, _goto_future, _setup

VALID_ALL_DISABLED_CONFIG = {
    DOMAIN: {
        CONF_USERNAME: "test",
        CONF_PASSWORD: "test",
        CONF_ROOM_CLIMATE: False,
        CONF_ZONE_CLIMATE: False,
    }
}


def _assert_room_state(hass, mode, hvac, temp, current_temp):
    """Assert room climate state."""
    state = hass.states.get("climate.vaillant_room_1")

    assert hass.states.is_state("climate.vaillant_room_1", hvac)
    assert state.attributes["current_temperature"] == current_temp
    assert state.attributes["max_temp"] == Room.MAX_TARGET_TEMP
    assert state.attributes["min_temp"] == Room.MIN_TARGET_TEMP
    assert state.attributes["temperature"] == temp
    assert set(state.attributes["hvac_modes"]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_AUTO,
        HVAC_MODE_OFF,
    }

    assert state.attributes[ATTR_VAILLANT_MODE] == mode.name


def _assert_zone_state(hass, mode, hvac, target_high, target_low,
                       current_temp):
    """Assert zone climate state."""
    state = hass.states.get("climate.vaillant_zone_1")

    assert hass.states.is_state("climate.vaillant_zone_1", hvac)
    assert state.attributes["current_temperature"] == current_temp
    assert state.attributes["max_temp"] == Zone.MAX_TARGET_TEMP
    assert state.attributes["min_temp"] == Zone.MIN_TARGET_TEMP
    assert state.attributes["target_temp_high"] == target_high
    assert state.attributes["target_temp_low"] == target_low
    assert set(state.attributes["hvac_modes"]) == {
        HVAC_MODE_OFF,
        HVAC_MODE_AUTO,
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL
    }

    assert state.attributes[ATTR_VAILLANT_MODE] == mode.name


@pytest.fixture(autouse=True)
def fixture_only_climate(mock_system_manager):
    """Mock vaillant to only handle sensor."""
    orig_platforms = vaillant.PLATFORMS
    vaillant.PLATFORMS = ["climate"]
    yield
    vaillant.PLATFORMS = orig_platforms


async def test_valid_config(hass):
    """Test setup with valid config."""
    assert await _setup(hass)
    assert len(hass.states.async_entity_ids()) == 2
    _assert_room_state(hass, OperatingModes.AUTO, HVAC_MODE_AUTO, 20, 22)
    _assert_zone_state(hass, OperatingModes.AUTO, HVAC_MODE_AUTO, 27, 22, 25)


async def test_valid_config_all_disabled(hass):
    """Test setup with valid config, but water heater disabled."""
    assert await _setup(hass, VALID_ALL_DISABLED_CONFIG)
    assert not hass.states.async_entity_ids()


async def test_empty_system(hass):
    """Test setup with empty system."""
    assert await _setup(
        hass, system=System(None, None, None, None, None, None, None, None,
                            None, None)
    )
    assert not hass.states.async_entity_ids()


async def test_state_update_room(hass):
    """Test room climate is updated accordingly to data."""
    assert await _setup(hass)
    _assert_room_state(hass, OperatingModes.AUTO, HVAC_MODE_AUTO,
                       20, 22)

    system = SystemManagerMock.system
    room = system.rooms[0]
    room.current_temperature = 25
    room.target_temperature = 30
    room.time_program = SystemManagerMock.time_program(SettingModes.ON, 30)
    await _goto_future(hass)

    _assert_room_state(hass, OperatingModes.AUTO, HVAC_MODE_AUTO,
                       30, 25)


async def test_room_heating_off(hass):
    """Test water heater is updated accordingly to data."""
    system = SystemManagerMock.get_default_system()
    system.rooms[0].operating_mode = OperatingModes.OFF

    assert await _setup(hass, system=system)
    _assert_room_state(hass, OperatingModes.OFF, HVAC_MODE_OFF,
                       Room.MIN_TARGET_TEMP, 22)


async def test_room_heating_manual(hass):
    """Test water heater is updated accordingly to data."""
    system = SystemManagerMock.get_default_system()
    system.rooms[0].operating_mode = OperatingModes.MANUAL

    assert await _setup(hass, system=system)
    _assert_room_state(hass, OperatingModes.MANUAL, HVAC_MODE_HEAT, 24, 22)


async def test_holiday_mode(hass):
    """Test holiday mode."""
    system = SystemManagerMock.get_default_system()
    system.quick_mode = QuickModes.HOLIDAY
    system.holiday_mode = HolidayMode(
        True, datetime.date.today(), datetime.date.today(), 15
    )

    assert await _setup(hass, system=system)
    _assert_room_state(hass, QuickModes.HOLIDAY, HVAC_MODE_OFF, 15, 22)


async def test_supported_features_all_modes_for_zone(hass):
    """Test supported features regarding of the operating mode."""
    system = SystemManagerMock.get_default_system()
    system.zones[0].operating_mode = OperatingModes.AUTO
    assert await _setup(hass, system=system)

    state = hass.states.get("climate.vaillant_zone_1")
    assert state.attributes["supported_features"] ==\
        SUPPORT_TARGET_TEMPERATURE_RANGE

    system.zones[0].operating_mode = OperatingModes.NIGHT
    await _goto_future(hass)
    state = hass.states.get("climate.vaillant_zone_1")
    assert state.attributes["supported_features"] == SUPPORT_TARGET_TEMPERATURE

    system.zones[0].operating_mode = OperatingModes.OFF
    await _goto_future(hass)
    state = hass.states.get("climate.vaillant_zone_1")
    assert state.attributes["supported_features"] == SUPPORT_TARGET_TEMPERATURE

    system.zones[0].operating_mode = OperatingModes.DAY
    await _goto_future(hass)
    state = hass.states.get("climate.vaillant_zone_1")
    assert state.attributes["supported_features"] == SUPPORT_TARGET_TEMPERATURE

    system.zones[0].operating_mode = OperatingModes.QUICK_VETO
    await _goto_future(hass)
    state = hass.states.get("climate.vaillant_zone_1")
    assert state.attributes["supported_features"] == SUPPORT_TARGET_TEMPERATURE

    system.zones[0].operating_mode = OperatingModes.OFF
    for mode in QuickModes._VALUES.values():
        system.quick_mode = mode

        if mode == QuickModes.HOLIDAY:
            start = datetime.date.today() - datetime.timedelta(days=1)
            end = datetime.date.today() + datetime.timedelta(days=1)
            system.holiday_mode = HolidayMode(True, start, end, 10)
        else:
            system.holiday_mode = HolidayMode(False, None, None, 10)

        await _goto_future(hass)
        state = hass.states.get("climate.vaillant_zone_1")
        assert state.attributes["supported_features"] == \
            SUPPORT_TARGET_TEMPERATURE


async def test_set_zone_target_high_temperature_quick_veto(hass):
    assert await _setup(hass)

    zone = SystemManagerMock.system.zones[0]
    low_temp = zone.target_min_temperature
    target_temp = SystemManagerMock.system.get_active_mode_zone(zone)\
        .target_temperature

    await hass.services.async_call('climate',
                                   'set_temperature',
                                   {
                                       'entity_id':
                                           'climate.vaillant_zone_1',
                                       'target_temp_high': 25,
                                       'temperature': target_temp,
                                       'target_temp_low':  low_temp
                                   })

    await hass.async_block_till_done()

    SystemManagerMock.instance.set_zone_quick_veto \
        .assert_called_once_with('zone_1', QuickVeto(None, 25.0))

    #
    # async def test_holiday_mode(hass):
    #     """Test holiday mode."""
    #     system = SystemManagerMock.get_default_system()
    #     system.quick_mode = QuickMode.QM_HOLIDAY
    #     system.holiday_mode = HolidayMode(True, datetime.date.today(),
    #                                       datetime.date.today(), 15)
    #
    #     assert await _setup(hass, system=system)
    #     _assert_state(hass, QuickMode.QM_HOLIDAY, HotWater.MIN_TEMP, 45, 'on')
    #
    #
    # async def test_away_mode(hass):
    #     """Test away mode."""
    #     system = SystemManagerMock.get_default_system()
    #     system.hot_water.operating_mode = HeatingMode.OFF
    #
    #     assert await _setup(hass, system=system)
    #     _assert_state(hass, HeatingMode.OFF, HotWater.MIN_TEMP, 45, 'on')
    #
    #
    # async def test_water_boost(hass):
    #     """Test hot water boost mode."""
    #     system = SystemManagerMock.get_default_system()
    #     system.quick_mode = QuickMode.QM_HOTWATER_BOOST
    #
    #     assert await _setup(hass, system=system)
    #     _assert_state(hass, QuickMode.QM_HOTWATER_BOOST, 40,
    #                   45, 'off')
    #
    #
    # async def test_system_off(hass):
    #     """Test system off mode."""
    #     system = SystemManagerMock.get_default_system()
    #     system.quick_mode = QuickMode.QM_SYSTEM_OFF
    #
    #     assert await _setup(hass, system=system)
    #     _assert_state(hass, QuickMode.QM_SYSTEM_OFF, HotWater.MIN_TEMP, 45, 'on')
    #
    #
    # async def test_one_day_away(hass):
    #     """Test one day away mode."""
    #     system = SystemManagerMock.get_default_system()
    #     system.quick_mode = QuickMode.QM_ONE_DAY_AWAY
    #
    #     assert await _setup(hass, system=system)
    #     _assert_state(hass, QuickMode.QM_ONE_DAY_AWAY, HotWater.MIN_TEMP, 45, 'on')
    #
    #
    # async def test_turn_away_mode_on(hass):
    #     """Test turn away mode on."""
    #     assert await _setup(hass)
    #
    #     hot_water = SystemManagerMock.system.hot_water
    #     hot_water.operating_mode = HeatingMode.OFF
    #     SystemManagerMock.instance.get_hot_water.return_value = hot_water
    #
    #     await hass.services.async_call('water_heater',
    #                                    'set_away_mode',
    #                                    {
    #                                        'entity_id':
    #                                            'water_heater.vaillant_hot_water',
    #                                        'away_mode': True
    #                                    })
    #     await hass.async_block_till_done()
    #
    #     SystemManagerMock.instance.set_hot_water_operating_mode.\
    #         assert_called_once_with(ANY, HeatingMode.OFF)
    #     _assert_state(hass, HeatingMode.OFF, HotWater.MIN_TEMP, 45, 'on')
    #
    #
    # async def test_turn_away_mode_off(hass):
    #     """Test turn away mode off."""
    #     assert await _setup(hass)
    #
    #     hot_water = SystemManagerMock.system.hot_water
    #     hot_water.operating_mode = HeatingMode.AUTO
    #     SystemManagerMock.instance.get_hot_water.return_value = hot_water
    #
    #     await hass.services.async_call('water_heater',
    #                                    'set_away_mode',
    #                                    {
    #                                        'entity_id':
    #                                            'water_heater.vaillant_hot_water',
    #                                        'away_mode': False
    #                                    })
    #     await hass.async_block_till_done()
    #
    #     SystemManagerMock.instance.set_hot_water_operating_mode.\
    #         assert_called_once_with(ANY, HeatingMode.AUTO)
    #
    #     _assert_state(hass, HeatingMode.AUTO, HotWater.MIN_TEMP, 45, 'off')
    #
    #
    # async def test_set_operating_mode(hass):
    #     """Test set operation mode."""
    #     assert await _setup(hass)
    #
    #     hot_water = SystemManagerMock.system.hot_water
    #     hot_water.operating_mode = HeatingMode.ON
    #     SystemManagerMock.instance.get_hot_water.return_value = hot_water
    #
    #     await hass.services.async_call('water_heater',
    #                                    'set_operating_mode',
    #                                    {
    #                                        'entity_id':
    #                                            'water_heater.vaillant_hot_water',
    #                                        'operating_mode': 'ON'
    #                                    })
    #     await hass.async_block_till_done()
    #
    #     SystemManagerMock.instance.set_hot_water_operating_mode\
    #         .assert_called_once_with(ANY, HeatingMode.ON)
    #     _assert_state(hass, HeatingMode.ON, 40, 45, 'off')
    #
    #
    # async def test_set_operating_mode_wrong(hass):
    #     """Test set operation mode with wrong mode."""
    #     assert await _setup(hass)
    #
    #     await hass.services.async_call('water_heater',
    #                                    'set_operating_mode',
    #                                    {
    #                                        'entity_id':
    #                                            'water_heater.vaillant_hot_water',
    #                                        'operating_mode': 'wrong'
    #                                    })
    #     await hass.async_block_till_done()
    #
    #     SystemManagerMock.instance.set_hot_water_operating_mode\
    #         .assert_not_called()
    #     _assert_state(hass, HeatingMode.AUTO, HotWater.MIN_TEMP, 45, 'off')
    #
    #
    # async def test_set_temperature(hass):
    #     """Test set target temperature."""
    #     system = SystemManagerMock.get_default_system()
    #     system.hot_water.operating_mode = HeatingMode.ON
    #     assert await _setup(hass, system=system)
    #
    #     SystemManagerMock.system.hot_water.target_temperature = 50
    #     SystemManagerMock.instance.get_hot_water.return_value = \
    #         SystemManagerMock.system.hot_water
    #
    #     await hass.services.async_call('water_heater',
    #                                    'set_temperature',
    #                                    {
    #                                        'entity_id':
    #                                            'water_heater.vaillant_hot_water',
    #                                        'temperature': 50
    #                                    })
    #     await hass.async_block_till_done()
    #
    #     SystemManagerMock.instance.set_hot_water_setpoint_temperature \
    #         .assert_called_once_with(ANY, 50)
    #     _assert_state(hass, HeatingMode.ON, 50, 45, 'off')
