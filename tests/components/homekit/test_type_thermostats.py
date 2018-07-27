"""Test different accessory types: Thermostats."""
from collections import namedtuple
from unittest.mock import patch

import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE, ATTR_MAX_TEMP, ATTR_MIN_TEMP, ATTR_TEMPERATURE,
    ATTR_TARGET_TEMP_LOW, ATTR_TARGET_TEMP_HIGH, ATTR_OPERATION_MODE,
    ATTR_OPERATION_LIST, DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP, DOMAIN,
    STATE_AUTO, STATE_COOL, STATE_HEAT)
from homeassistant.components.homekit.const import (
    PROP_MAX_VALUE, PROP_MIN_VALUE)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, ATTR_UNIT_OF_MEASUREMENT,
    CONF_TEMPERATURE_UNIT, STATE_OFF, TEMP_CELSIUS, TEMP_FAHRENHEIT)

from tests.common import async_mock_service
from tests.components.homekit.common import patch_debounce


@pytest.fixture(scope='module')
def cls():
    """Patch debounce decorator during import of type_thermostats."""
    patcher = patch_debounce()
    patcher.start()
    _import = __import__('homeassistant.components.homekit.type_thermostats',
                         fromlist=['Thermostat'])
    patcher_tuple = namedtuple('Cls', ['thermostat'])
    yield patcher_tuple(thermostat=_import.Thermostat)
    patcher.stop()


async def test_default_thermostat(hass, hk_driver, cls):
    """Test if accessory and HA are updated accordingly."""
    entity_id = 'climate.test'

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    acc = cls.thermostat(hass, hk_driver, 'Climate', entity_id, 2, None)
    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 9  # Thermostat

    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 0
    assert acc.char_current_temp.value == 21.0
    assert acc.char_target_temp.value == 21.0
    assert acc.char_display_units.value == 0
    assert acc.char_cooling_thresh_temp is None
    assert acc.char_heating_thresh_temp is None

    assert acc.char_target_temp.properties[PROP_MAX_VALUE] == DEFAULT_MAX_TEMP
    assert acc.char_target_temp.properties[PROP_MIN_VALUE] == DEFAULT_MIN_TEMP

    hass.states.async_set(entity_id, STATE_HEAT,
                          {ATTR_OPERATION_MODE: STATE_HEAT,
                           ATTR_TEMPERATURE: 22.0,
                           ATTR_CURRENT_TEMPERATURE: 18.0,
                           ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 1
    assert acc.char_target_heat_cool.value == 1
    assert acc.char_current_temp.value == 18.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(entity_id, STATE_HEAT,
                          {ATTR_OPERATION_MODE: STATE_HEAT,
                           ATTR_TEMPERATURE: 22.0,
                           ATTR_CURRENT_TEMPERATURE: 23.0,
                           ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 1
    assert acc.char_current_temp.value == 23.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(entity_id, STATE_COOL,
                          {ATTR_OPERATION_MODE: STATE_COOL,
                           ATTR_TEMPERATURE: 20.0,
                           ATTR_CURRENT_TEMPERATURE: 25.0,
                           ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 20.0
    assert acc.char_current_heat_cool.value == 2
    assert acc.char_target_heat_cool.value == 2
    assert acc.char_current_temp.value == 25.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(entity_id, STATE_COOL,
                          {ATTR_OPERATION_MODE: STATE_COOL,
                           ATTR_TEMPERATURE: 20.0,
                           ATTR_CURRENT_TEMPERATURE: 19.0,
                           ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 20.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 2
    assert acc.char_current_temp.value == 19.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(entity_id, STATE_OFF,
                          {ATTR_OPERATION_MODE: STATE_OFF,
                           ATTR_TEMPERATURE: 22.0,
                           ATTR_CURRENT_TEMPERATURE: 18.0,
                           ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
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
                           ATTR_CURRENT_TEMPERATURE: 18.0,
                           ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
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
                           ATTR_CURRENT_TEMPERATURE: 25.0,
                           ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
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
                           ATTR_CURRENT_TEMPERATURE: 22.0,
                           ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 22.0
    assert acc.char_display_units.value == 0

    # Set from HomeKit
    call_set_temperature = async_mock_service(hass, DOMAIN, 'set_temperature')
    call_set_operation_mode = async_mock_service(hass, DOMAIN,
                                                 'set_operation_mode')

    await hass.async_add_job(acc.char_target_temp.client_update_value, 19.0)
    await hass.async_block_till_done()
    assert call_set_temperature
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TEMPERATURE] == 19.0
    assert acc.char_target_temp.value == 19.0

    await hass.async_add_job(acc.char_target_heat_cool.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_set_operation_mode
    assert call_set_operation_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_operation_mode[0].data[ATTR_OPERATION_MODE] == STATE_HEAT
    assert acc.char_target_heat_cool.value == 1


async def test_auto_thermostat(hass, hk_driver, cls):
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
    assert acc.char_heating_thresh_temp.properties[PROP_MAX_VALUE] \
        == DEFAULT_MAX_TEMP
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_VALUE] \
        == DEFAULT_MIN_TEMP

    hass.states.async_set(entity_id, STATE_AUTO,
                          {ATTR_OPERATION_MODE: STATE_AUTO,
                           ATTR_TARGET_TEMP_HIGH: 22.0,
                           ATTR_TARGET_TEMP_LOW: 20.0,
                           ATTR_CURRENT_TEMPERATURE: 18.0,
                           ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
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
                           ATTR_CURRENT_TEMPERATURE: 24.0,
                           ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
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
                           ATTR_CURRENT_TEMPERATURE: 21.0,
                           ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 19.0
    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 21.0
    assert acc.char_display_units.value == 0

    # Set from HomeKit
    call_set_temperature = async_mock_service(hass, DOMAIN, 'set_temperature')

    await hass.async_add_job(
        acc.char_heating_thresh_temp.client_update_value, 20.0)
    await hass.async_block_till_done()
    assert call_set_temperature[0]
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_LOW] == 20.0
    assert acc.char_heating_thresh_temp.value == 20.0

    await hass.async_add_job(
        acc.char_cooling_thresh_temp.client_update_value, 25.0)
    await hass.async_block_till_done()
    assert call_set_temperature[1]
    assert call_set_temperature[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[1].data[ATTR_TARGET_TEMP_HIGH] == 25.0
    assert acc.char_cooling_thresh_temp.value == 25.0


async def test_power_state(hass, hk_driver, cls):
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
    call_turn_on = async_mock_service(hass, DOMAIN, 'turn_on')
    call_turn_off = async_mock_service(hass, DOMAIN, 'turn_off')
    call_set_operation_mode = async_mock_service(hass, DOMAIN,
                                                 'set_operation_mode')

    await hass.async_add_job(acc.char_target_heat_cool.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_operation_mode
    assert call_set_operation_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_operation_mode[0].data[ATTR_OPERATION_MODE] == STATE_HEAT
    assert acc.char_target_heat_cool.value == 1

    await hass.async_add_job(acc.char_target_heat_cool.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_target_heat_cool.value == 0


async def test_thermostat_fahrenheit(hass, hk_driver, cls):
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
                           ATTR_TARGET_TEMP_LOW: 68,
                           ATTR_TEMPERATURE: 71.6,
                           ATTR_CURRENT_TEMPERATURE: 73.4,
                           ATTR_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT})
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 20.0
    assert acc.char_cooling_thresh_temp.value == 24.0
    assert acc.char_current_temp.value == 23.0
    assert acc.char_target_temp.value == 22.0
    assert acc.char_display_units.value == 1

    # Set from HomeKit
    call_set_temperature = async_mock_service(hass, DOMAIN, 'set_temperature')

    await hass.async_add_job(
        acc.char_cooling_thresh_temp.client_update_value, 23)
    await hass.async_block_till_done()
    assert call_set_temperature[0]
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_HIGH] == 73.4
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_LOW] == 68

    await hass.async_add_job(
        acc.char_heating_thresh_temp.client_update_value, 22)
    await hass.async_block_till_done()
    assert call_set_temperature[1]
    assert call_set_temperature[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[1].data[ATTR_TARGET_TEMP_HIGH] == 73.4
    assert call_set_temperature[1].data[ATTR_TARGET_TEMP_LOW] == 71.6

    await hass.async_add_job(acc.char_target_temp.client_update_value, 24.0)
    await hass.async_block_till_done()
    assert call_set_temperature[2]
    assert call_set_temperature[2].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[2].data[ATTR_TEMPERATURE] == 75.2


async def test_get_temperature_range(hass, hk_driver, cls):
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
    assert acc.get_temperature_range() == (15.6, 21.1)
