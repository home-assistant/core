"""Test different accessory types: Thermostats."""
from collections import namedtuple
from unittest.mock import patch

import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE, ATTR_MAX_TEMP, ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_LOW, ATTR_TARGET_TEMP_HIGH, ATTR_OPERATION_MODE,
    ATTR_OPERATION_LIST, DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP,
    DOMAIN as DOMAIN_CLIMATE, STATE_AUTO, STATE_COOL, STATE_HEAT)
from homeassistant.components.homekit.const import (
    ATTR_VALUE, DEFAULT_MAX_TEMP_WATER_HEATER, DEFAULT_MIN_TEMP_WATER_HEATER,
    PROP_MAX_VALUE, PROP_MIN_STEP, PROP_MIN_VALUE)
from homeassistant.components.water_heater import (
    DOMAIN as DOMAIN_WATER_HEATER)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_TEMPERATURE, ATTR_SUPPORTED_FEATURES,
    CONF_TEMPERATURE_UNIT, STATE_OFF, TEMP_FAHRENHEIT)

from tests.common import async_mock_service
from tests.components.homekit.common import patch_debounce


@pytest.fixture(scope='module')
def cls():
    """Patch debounce decorator during import of type_thermostats."""
    patcher = patch_debounce()
    patcher.start()
    _import = __import__('homeassistant.components.homekit.type_thermostats',
                         fromlist=['Thermostat', 'WaterHeater'])
    patcher_tuple = namedtuple('Cls', ['thermostat', 'water_heater'])
    yield patcher_tuple(thermostat=_import.Thermostat,
                        water_heater=_import.WaterHeater)
    patcher.stop()


async def test_thermostat(hass, hk_driver, cls, events):
    """Test if accessory and HA are updated accordingly."""
    entity_id = 'climate.test'

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    acc = cls.thermostat(hass, hk_driver, 'Climate', entity_id, 2, None)
    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 9  # Thermostat

    assert acc.get_temperature_range() == (7.0, 35.0)
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 0
    assert acc.char_current_temp.value == 21.0
    assert acc.char_target_temp.value == 21.0
    assert acc.char_display_units.value == 0
    assert acc.char_cooling_thresh_temp is None
    assert acc.char_heating_thresh_temp is None

    assert acc.char_target_temp.properties[PROP_MAX_VALUE] == DEFAULT_MAX_TEMP
    assert acc.char_target_temp.properties[PROP_MIN_VALUE] == DEFAULT_MIN_TEMP
    assert acc.char_target_temp.properties[PROP_MIN_STEP] == 0.5

    hass.states.async_set(entity_id, STATE_HEAT,
                          {ATTR_OPERATION_MODE: STATE_HEAT,
                           ATTR_TEMPERATURE: 22.2,
                           ATTR_CURRENT_TEMPERATURE: 17.8})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 1
    assert acc.char_target_heat_cool.value == 1
    assert acc.char_current_temp.value == 18.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(entity_id, STATE_HEAT,
                          {ATTR_OPERATION_MODE: STATE_HEAT,
                           ATTR_TEMPERATURE: 22.0,
                           ATTR_CURRENT_TEMPERATURE: 23.0})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 1
    assert acc.char_current_temp.value == 23.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(entity_id, STATE_COOL,
                          {ATTR_OPERATION_MODE: STATE_COOL,
                           ATTR_TEMPERATURE: 20.0,
                           ATTR_CURRENT_TEMPERATURE: 25.0})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 20.0
    assert acc.char_current_heat_cool.value == 2
    assert acc.char_target_heat_cool.value == 2
    assert acc.char_current_temp.value == 25.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(entity_id, STATE_COOL,
                          {ATTR_OPERATION_MODE: STATE_COOL,
                           ATTR_TEMPERATURE: 20.0,
                           ATTR_CURRENT_TEMPERATURE: 19.0})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 20.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 2
    assert acc.char_current_temp.value == 19.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(entity_id, STATE_OFF,
                          {ATTR_OPERATION_MODE: STATE_OFF,
                           ATTR_TEMPERATURE: 22.0,
                           ATTR_CURRENT_TEMPERATURE: 18.0})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 0
    assert acc.char_current_temp.value == 18.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(entity_id, STATE_AUTO,
                          {ATTR_OPERATION_MODE: STATE_AUTO,
                           ATTR_OPERATION_LIST: [STATE_HEAT, STATE_COOL],
                           ATTR_TEMPERATURE: 22.0,
                           ATTR_CURRENT_TEMPERATURE: 18.0})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 1
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 18.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(entity_id, STATE_AUTO,
                          {ATTR_OPERATION_MODE: STATE_AUTO,
                           ATTR_OPERATION_LIST: [STATE_HEAT, STATE_COOL],
                           ATTR_TEMPERATURE: 22.0,
                           ATTR_CURRENT_TEMPERATURE: 25.0})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 2
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 25.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(entity_id, STATE_AUTO,
                          {ATTR_OPERATION_MODE: STATE_AUTO,
                           ATTR_OPERATION_LIST: [STATE_HEAT, STATE_COOL],
                           ATTR_TEMPERATURE: 22.0,
                           ATTR_CURRENT_TEMPERATURE: 22.0})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 22.0
    assert acc.char_display_units.value == 0

    # Set from HomeKit
    call_set_temperature = async_mock_service(hass, DOMAIN_CLIMATE,
                                              'set_temperature')
    call_set_operation_mode = async_mock_service(hass, DOMAIN_CLIMATE,
                                                 'set_operation_mode')

    await hass.async_add_job(acc.char_target_temp.client_update_value, 19.0)
    await hass.async_block_till_done()
    assert call_set_temperature
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TEMPERATURE] == 19.0
    assert acc.char_target_temp.value == 19.0
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == '19.0°C'

    await hass.async_add_job(acc.char_target_heat_cool.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_set_operation_mode
    assert call_set_operation_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_operation_mode[0].data[ATTR_OPERATION_MODE] == STATE_HEAT
    assert acc.char_target_heat_cool.value == 1
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == STATE_HEAT


async def test_thermostat_auto(hass, hk_driver, cls, events):
    """Test if accessory and HA are updated accordingly."""
    entity_id = 'climate.test'

    # support_auto = True
    hass.states.async_set(entity_id, STATE_OFF, {ATTR_SUPPORTED_FEATURES: 6})
    await hass.async_block_till_done()
    acc = cls.thermostat(hass, hk_driver, 'Climate', entity_id, 2, None)
    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()

    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_heating_thresh_temp.value == 19.0

    assert acc.char_cooling_thresh_temp.properties[PROP_MAX_VALUE] \
        == DEFAULT_MAX_TEMP
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_VALUE] \
        == DEFAULT_MIN_TEMP
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_STEP] == 0.5
    assert acc.char_heating_thresh_temp.properties[PROP_MAX_VALUE] \
        == DEFAULT_MAX_TEMP
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_VALUE] \
        == DEFAULT_MIN_TEMP
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_STEP] == 0.5

    hass.states.async_set(entity_id, STATE_AUTO,
                          {ATTR_OPERATION_MODE: STATE_AUTO,
                           ATTR_TARGET_TEMP_HIGH: 22.0,
                           ATTR_TARGET_TEMP_LOW: 20.0,
                           ATTR_CURRENT_TEMPERATURE: 18.0})
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 20.0
    assert acc.char_cooling_thresh_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 1
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 18.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(entity_id, STATE_AUTO,
                          {ATTR_OPERATION_MODE: STATE_AUTO,
                           ATTR_TARGET_TEMP_HIGH: 23.0,
                           ATTR_TARGET_TEMP_LOW: 19.0,
                           ATTR_CURRENT_TEMPERATURE: 24.0})
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 19.0
    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_current_heat_cool.value == 2
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 24.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(entity_id, STATE_AUTO,
                          {ATTR_OPERATION_MODE: STATE_AUTO,
                           ATTR_TARGET_TEMP_HIGH: 23.0,
                           ATTR_TARGET_TEMP_LOW: 19.0,
                           ATTR_CURRENT_TEMPERATURE: 21.0})
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 19.0
    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 21.0
    assert acc.char_display_units.value == 0

    # Set from HomeKit
    call_set_temperature = async_mock_service(hass, DOMAIN_CLIMATE,
                                              'set_temperature')

    await hass.async_add_job(
        acc.char_heating_thresh_temp.client_update_value, 20.0)
    await hass.async_block_till_done()
    assert call_set_temperature[0]
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_LOW] == 20.0
    assert acc.char_heating_thresh_temp.value == 20.0
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == 'heating threshold 20.0°C'

    await hass.async_add_job(
        acc.char_cooling_thresh_temp.client_update_value, 25.0)
    await hass.async_block_till_done()
    assert call_set_temperature[1]
    assert call_set_temperature[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[1].data[ATTR_TARGET_TEMP_HIGH] == 25.0
    assert acc.char_cooling_thresh_temp.value == 25.0
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == 'cooling threshold 25.0°C'


async def test_thermostat_power_state(hass, hk_driver, cls, events):
    """Test if accessory and HA are updated accordingly."""
    entity_id = 'climate.test'

    # SUPPORT_ON_OFF = True
    hass.states.async_set(entity_id, STATE_HEAT,
                          {ATTR_SUPPORTED_FEATURES: 4096,
                           ATTR_OPERATION_MODE: STATE_HEAT,
                           ATTR_TEMPERATURE: 23.0,
                           ATTR_CURRENT_TEMPERATURE: 18.0})
    await hass.async_block_till_done()
    acc = cls.thermostat(hass, hk_driver, 'Climate', entity_id, 2, None)
    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.support_power_state is True

    assert acc.char_current_heat_cool.value == 1
    assert acc.char_target_heat_cool.value == 1

    hass.states.async_set(entity_id, STATE_OFF,
                          {ATTR_OPERATION_MODE: STATE_HEAT,
                           ATTR_TEMPERATURE: 23.0,
                           ATTR_CURRENT_TEMPERATURE: 18.0})
    await hass.async_block_till_done()
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 0

    hass.states.async_set(entity_id, STATE_OFF,
                          {ATTR_OPERATION_MODE: STATE_OFF,
                           ATTR_TEMPERATURE: 23.0,
                           ATTR_CURRENT_TEMPERATURE: 18.0})
    await hass.async_block_till_done()
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 0

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN_CLIMATE, 'turn_on')
    call_turn_off = async_mock_service(hass, DOMAIN_CLIMATE, 'turn_off')
    call_set_operation_mode = async_mock_service(hass, DOMAIN_CLIMATE,
                                                 'set_operation_mode')

    await hass.async_add_job(acc.char_target_heat_cool.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_operation_mode
    assert call_set_operation_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_operation_mode[0].data[ATTR_OPERATION_MODE] == STATE_HEAT
    assert acc.char_target_heat_cool.value == 1
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == STATE_HEAT

    await hass.async_add_job(acc.char_target_heat_cool.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_target_heat_cool.value == 0
    assert len(events) == 3
    assert events[-1].data[ATTR_VALUE] is None


async def test_thermostat_fahrenheit(hass, hk_driver, cls, events):
    """Test if accessory and HA are updated accordingly."""
    entity_id = 'climate.test'

    # support_auto = True
    hass.states.async_set(entity_id, STATE_OFF, {ATTR_SUPPORTED_FEATURES: 6})
    await hass.async_block_till_done()
    with patch.object(hass.config.units, CONF_TEMPERATURE_UNIT,
                      new=TEMP_FAHRENHEIT):
        acc = cls.thermostat(hass, hk_driver, 'Climate', entity_id, 2, None)
    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()

    hass.states.async_set(entity_id, STATE_AUTO,
                          {ATTR_OPERATION_MODE: STATE_AUTO,
                           ATTR_TARGET_TEMP_HIGH: 75.2,
                           ATTR_TARGET_TEMP_LOW: 68.1,
                           ATTR_TEMPERATURE: 71.6,
                           ATTR_CURRENT_TEMPERATURE: 73.4})
    await hass.async_block_till_done()
    assert acc.get_temperature_range() == (7.0, 35.0)
    assert acc.char_heating_thresh_temp.value == 20.0
    assert acc.char_cooling_thresh_temp.value == 24.0
    assert acc.char_current_temp.value == 23.0
    assert acc.char_target_temp.value == 22.0
    assert acc.char_display_units.value == 1

    # Set from HomeKit
    call_set_temperature = async_mock_service(hass, DOMAIN_CLIMATE,
                                              'set_temperature')

    await hass.async_add_job(
        acc.char_cooling_thresh_temp.client_update_value, 23)
    await hass.async_block_till_done()
    assert call_set_temperature[0]
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_HIGH] == 73.5
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_LOW] == 68
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == 'cooling threshold 73.5°F'

    await hass.async_add_job(
        acc.char_heating_thresh_temp.client_update_value, 22)
    await hass.async_block_till_done()
    assert call_set_temperature[1]
    assert call_set_temperature[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[1].data[ATTR_TARGET_TEMP_HIGH] == 73.5
    assert call_set_temperature[1].data[ATTR_TARGET_TEMP_LOW] == 71.5
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == 'heating threshold 71.5°F'

    await hass.async_add_job(acc.char_target_temp.client_update_value, 24.0)
    await hass.async_block_till_done()
    assert call_set_temperature[2]
    assert call_set_temperature[2].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[2].data[ATTR_TEMPERATURE] == 75.0
    assert len(events) == 3
    assert events[-1].data[ATTR_VALUE] == '75.0°F'


async def test_thermostat_get_temperature_range(hass, hk_driver, cls):
    """Test if temperature range is evaluated correctly."""
    entity_id = 'climate.test'

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    acc = cls.thermostat(hass, hk_driver, 'Climate', entity_id, 2, None)

    hass.states.async_set(entity_id, STATE_OFF,
                          {ATTR_MIN_TEMP: 20, ATTR_MAX_TEMP: 25})
    await hass.async_block_till_done()
    assert acc.get_temperature_range() == (20, 25)

    acc._unit = TEMP_FAHRENHEIT
    hass.states.async_set(entity_id, STATE_OFF,
                          {ATTR_MIN_TEMP: 60, ATTR_MAX_TEMP: 70})
    await hass.async_block_till_done()
    assert acc.get_temperature_range() == (15.5, 21.0)


async def test_water_heater(hass, hk_driver, cls, events):
    """Test if accessory and HA are updated accordingly."""
    entity_id = 'water_heater.test'

    hass.states.async_set(entity_id, STATE_HEAT)
    await hass.async_block_till_done()
    acc = cls.water_heater(hass, hk_driver, 'WaterHeater', entity_id, 2, None)
    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 9  # Thermostat

    assert acc.char_current_heat_cool.value == 1  # Heat
    assert acc.char_target_heat_cool.value == 1  # Heat
    assert acc.char_current_temp.value == 50.0
    assert acc.char_target_temp.value == 50.0
    assert acc.char_display_units.value == 0

    assert acc.char_target_temp.properties[PROP_MAX_VALUE] == \
        DEFAULT_MAX_TEMP_WATER_HEATER
    assert acc.char_target_temp.properties[PROP_MIN_VALUE] == \
        DEFAULT_MIN_TEMP_WATER_HEATER
    assert acc.char_target_temp.properties[PROP_MIN_STEP] == 0.5

    hass.states.async_set(entity_id, STATE_HEAT,
                          {ATTR_OPERATION_MODE: STATE_HEAT,
                           ATTR_TEMPERATURE: 56.0})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 56.0
    assert acc.char_current_temp.value == 56.0
    assert acc.char_target_heat_cool.value == 1
    assert acc.char_current_heat_cool.value == 1
    assert acc.char_display_units.value == 0

    hass.states.async_set(entity_id, STATE_AUTO,
                          {ATTR_OPERATION_MODE: STATE_AUTO})
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1
    assert acc.char_current_heat_cool.value == 1

    # Set from HomeKit
    call_set_temperature = async_mock_service(hass, DOMAIN_WATER_HEATER,
                                              'set_temperature')

    await hass.async_add_job(acc.char_target_temp.client_update_value, 52.0)
    await hass.async_block_till_done()
    assert call_set_temperature
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TEMPERATURE] == 52.0
    assert acc.char_target_temp.value == 52.0
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == '52.0°C'

    await hass.async_add_job(acc.char_target_heat_cool.client_update_value, 0)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    await hass.async_add_job(acc.char_target_heat_cool.client_update_value, 2)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    await hass.async_add_job(acc.char_target_heat_cool.client_update_value, 3)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1


async def test_water_heater_fahrenheit(hass, hk_driver, cls, events):
    """Test if accessory and HA are update accordingly."""
    entity_id = 'water_heater.test'

    hass.states.async_set(entity_id, STATE_HEAT)
    await hass.async_block_till_done()
    with patch.object(hass.config.units, CONF_TEMPERATURE_UNIT,
                      new=TEMP_FAHRENHEIT):
        acc = cls.water_heater(hass, hk_driver, 'WaterHeater',
                               entity_id, 2, None)
    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()

    hass.states.async_set(entity_id, STATE_HEAT,
                          {ATTR_TEMPERATURE: 131})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 55.0
    assert acc.char_current_temp.value == 55.0
    assert acc.char_display_units.value == 1

    # Set from HomeKit
    call_set_temperature = async_mock_service(hass, DOMAIN_WATER_HEATER,
                                              'set_temperature')

    await hass.async_add_job(acc.char_target_temp.client_update_value, 60)
    await hass.async_block_till_done()
    assert call_set_temperature
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TEMPERATURE] == 140.0
    assert acc.char_target_temp.value == 60.0
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == '140.0°F'


async def test_water_heater_get_temperature_range(hass, hk_driver, cls):
    """Test if temperature range is evaluated correctly."""
    entity_id = 'water_heater.test'

    hass.states.async_set(entity_id, STATE_HEAT)
    await hass.async_block_till_done()
    acc = cls.thermostat(hass, hk_driver, 'WaterHeater', entity_id, 2, None)

    hass.states.async_set(entity_id, STATE_HEAT,
                          {ATTR_MIN_TEMP: 20, ATTR_MAX_TEMP: 25})
    await hass.async_block_till_done()
    assert acc.get_temperature_range() == (20, 25)

    acc._unit = TEMP_FAHRENHEIT
    hass.states.async_set(entity_id, STATE_OFF,
                          {ATTR_MIN_TEMP: 60, ATTR_MAX_TEMP: 70})
    await hass.async_block_till_done()
    assert acc.get_temperature_range() == (15.5, 21.0)
