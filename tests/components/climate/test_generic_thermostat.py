"""The tests for the generic_thermostat."""
import datetime
import pytest
from asynctest import mock
import pytz

import homeassistant.core as ha
from homeassistant.core import (
    callback, DOMAIN as HASS_DOMAIN, CoreState, State)
from homeassistant.setup import async_setup_component
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_OFF,
    STATE_IDLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    ATTR_TEMPERATURE
)
from homeassistant import loader
from homeassistant.util.unit_system import METRIC_SYSTEM
from homeassistant.components import climate, input_boolean, switch
from homeassistant.components.climate import STATE_HEAT, STATE_COOL
import homeassistant.components as comps
from tests.common import assert_setup_component, mock_restore_cache
from tests.components.climate import common


ENTITY = 'climate.test'
ENT_SENSOR = 'sensor.test'
ENT_SWITCH = 'switch.test'
HEAT_ENTITY = 'climate.test_heat'
COOL_ENTITY = 'climate.test_cool'
ATTR_AWAY_MODE = 'away_mode'
MIN_TEMP = 3.0
MAX_TEMP = 65.0
TARGET_TEMP = 42.0
COLD_TOLERANCE = 0.5
HOT_TOLERANCE = 0.5


async def test_setup_missing_conf(hass):
    """Test set up heat_control with missing config values."""
    config = {
        'name': 'test',
        'target_sensor': ENT_SENSOR
    }
    with assert_setup_component(0):
        await async_setup_component(hass, 'climate', {
            'climate': config})


async def test_valid_conf(hass):
    """Test set up generic_thermostat with valid config values."""
    assert await async_setup_component(hass, 'climate', {
        'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR
        }})


@pytest.fixture
def setup_comp_1(hass):
    """Initialize components."""
    hass.config.units = METRIC_SYSTEM
    assert hass.loop.run_until_complete(
        comps.async_setup(hass, {})
    )


async def test_heater_input_boolean(hass, setup_comp_1):
    """Test heater switching input_boolean."""
    heater_switch = 'input_boolean.test'
    assert await async_setup_component(hass, input_boolean.DOMAIN, {
        'input_boolean': {'test': None}})

    assert await async_setup_component(hass, climate.DOMAIN, {'climate': {
        'platform': 'generic_thermostat',
        'name': 'test',
        'heater': heater_switch,
        'target_sensor': ENT_SENSOR
    }})

    assert STATE_OFF == \
        hass.states.get(heater_switch).state

    _setup_sensor(hass, 18)
    await hass.async_block_till_done()
    common.async_set_temperature(hass, 23)
    await hass.async_block_till_done()

    assert STATE_ON == \
        hass.states.get(heater_switch).state


async def test_heater_switch(hass, setup_comp_1):
    """Test heater switching test switch."""
    platform = loader.get_component(hass, 'switch.test')
    platform.init()
    switch_1 = platform.DEVICES[1]
    assert await async_setup_component(hass, switch.DOMAIN, {'switch': {
        'platform': 'test'}})
    heater_switch = switch_1.entity_id

    assert await async_setup_component(hass, climate.DOMAIN, {'climate': {
        'platform': 'generic_thermostat',
        'name': 'test',
        'heater': heater_switch,
        'target_sensor': ENT_SENSOR
    }})

    assert STATE_OFF == \
        hass.states.get(heater_switch).state

    _setup_sensor(hass, 18)
    await hass.async_block_till_done()
    common.async_set_temperature(hass, 23)
    await hass.async_block_till_done()

    assert STATE_ON == \
        hass.states.get(heater_switch).state


def _setup_sensor(hass, temp):
    """Set up the test sensor."""
    hass.states.async_set(ENT_SENSOR, temp)


@pytest.fixture
def setup_comp_2(hass):
    """Initialize components."""
    hass.config.units = METRIC_SYSTEM
    assert hass.loop.run_until_complete(async_setup_component(
        hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'cold_tolerance': 2,
            'hot_tolerance': 4,
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'away_temp': 16
        }}))


async def test_setup_defaults_to_unknown(hass, setup_comp_2):
    """Test the setting of defaults to unknown."""
    assert STATE_IDLE == hass.states.get(ENTITY).state


async def test_default_setup_params(hass, setup_comp_2):
    """Test the setup with default parameters."""
    state = hass.states.get(ENTITY)
    assert 7 == state.attributes.get('min_temp')
    assert 35 == state.attributes.get('max_temp')
    assert 7 == state.attributes.get('temperature')


async def test_get_operation_modes(hass, setup_comp_2):
    """Test that the operation list returns the correct modes."""
    state = hass.states.get(ENTITY)
    modes = state.attributes.get('operation_list')
    assert [climate.STATE_HEAT, STATE_OFF] == modes


async def test_set_target_temp(hass, setup_comp_2):
    """Test the setting of the target temperature."""
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert 30.0 == state.attributes.get('temperature')
    common.async_set_temperature(hass, None)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert 30.0 == state.attributes.get('temperature')


async def test_set_away_mode(hass, setup_comp_2):
    """Test the setting away mode."""
    common.async_set_temperature(hass, 23)
    await hass.async_block_till_done()
    common.async_set_away_mode(hass, True)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert 16 == state.attributes.get('temperature')


async def test_set_away_mode_and_restore_prev_temp(hass, setup_comp_2):
    """Test the setting and removing away mode.

    Verify original temperature is restored.
    """
    common.async_set_temperature(hass, 23)
    await hass.async_block_till_done()
    common.async_set_away_mode(hass, True)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert 16 == state.attributes.get('temperature')
    common.async_set_away_mode(hass, False)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert 23 == state.attributes.get('temperature')


async def test_set_away_mode_twice_and_restore_prev_temp(hass, setup_comp_2):
    """Test the setting away mode twice in a row.

    Verify original temperature is restored.
    """
    common.async_set_temperature(hass, 23)
    await hass.async_block_till_done()
    common.async_set_away_mode(hass, True)
    await hass.async_block_till_done()
    common.async_set_away_mode(hass, True)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert 16 == state.attributes.get('temperature')
    common.async_set_away_mode(hass, False)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert 23 == state.attributes.get('temperature')


async def test_sensor_bad_value(hass, setup_comp_2):
    """Test sensor that have None as state."""
    state = hass.states.get(ENTITY)
    temp = state.attributes.get('current_temperature')

    _setup_sensor(hass, None)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY)
    assert temp == state.attributes.get('current_temperature')


async def test_set_target_temp_heater_on(hass, setup_comp_2):
    """Test if target temperature turn heater on."""
    calls = _setup_switch(hass, False)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_set_target_temp_heater_off(hass, setup_comp_2):
    """Test if target temperature turn heater off."""
    calls = _setup_switch(hass, True)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    assert 2 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_temp_change_heater_on_within_tolerance(hass, setup_comp_2):
    """Test if temperature change doesn't turn on within tolerance."""
    calls = _setup_switch(hass, False)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    _setup_sensor(hass, 29)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_temp_change_heater_on_outside_tolerance(hass, setup_comp_2):
    """Test if temperature change turn heater on outside cold tolerance."""
    calls = _setup_switch(hass, False)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    _setup_sensor(hass, 27)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_temp_change_heater_off_within_tolerance(hass, setup_comp_2):
    """Test if temperature change doesn't turn off within tolerance."""
    calls = _setup_switch(hass, True)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    _setup_sensor(hass, 33)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_temp_change_heater_off_outside_tolerance(hass, setup_comp_2):
    """Test if temperature change turn heater off outside hot tolerance."""
    calls = _setup_switch(hass, True)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_running_when_operating_mode_is_off(hass, setup_comp_2):
    """Test that the switch turns off when enabled is set False."""
    calls = _setup_switch(hass, True)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    common.async_set_operation_mode(hass, STATE_OFF)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_no_state_change_when_operation_mode_off(hass, setup_comp_2):
    """Test that the switch doesn't turn on when enabled is False."""
    calls = _setup_switch(hass, False)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    common.async_set_operation_mode(hass, STATE_OFF)
    await hass.async_block_till_done()
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 0 == len(calls)


@mock.patch('logging.Logger.error')
async def test_invalid_operating_mode(log_mock, hass, setup_comp_2):
    """Test error handling for invalid operation mode."""
    common.async_set_operation_mode(hass, 'invalid mode')
    await hass.async_block_till_done()
    assert log_mock.call_count == 1


async def test_operating_mode_heat(hass, setup_comp_2):
    """Test change mode from OFF to HEAT.

    Switch turns on when temp below setpoint and mode changes.
    """
    common.async_set_operation_mode(hass, STATE_OFF)
    common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    calls = _setup_switch(hass, False)
    common.async_set_operation_mode(hass, climate.STATE_HEAT)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data['entity_id']


def _setup_switch(hass, is_on):
    """Set up the test switch."""
    hass.states.async_set(ENT_SWITCH, STATE_ON if is_on else STATE_OFF)
    calls = []

    @callback
    def log_call(call):
        """Log service calls."""
        calls.append(call)

    hass.services.async_register(ha.DOMAIN, SERVICE_TURN_ON, log_call)
    hass.services.async_register(ha.DOMAIN, SERVICE_TURN_OFF, log_call)

    return calls


@pytest.fixture
def setup_comp_3(hass):
    """Initialize components."""
    hass.config.temperature_unit = TEMP_CELSIUS
    assert hass.loop.run_until_complete(async_setup_component(
        hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'cold_tolerance': 2,
            'hot_tolerance': 4,
            'away_temp': 30,
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'ac_mode': True
        }}))


async def test_set_target_temp_ac_off(hass, setup_comp_3):
    """Test if target temperature turn ac off."""
    calls = _setup_switch(hass, True)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    assert 2 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_turn_away_mode_on_cooling(hass, setup_comp_3):
    """Test the setting away mode when cooling."""
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    common.async_set_temperature(hass, 19)
    await hass.async_block_till_done()
    common.async_set_away_mode(hass, True)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert 30 == state.attributes.get('temperature')


async def test_operating_mode_cool(hass, setup_comp_3):
    """Test change mode from OFF to COOL.

    Switch turns on when temp below setpoint and mode changes.
    """
    common.async_set_operation_mode(hass, STATE_OFF)
    common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    calls = _setup_switch(hass, False)
    common.async_set_operation_mode(hass, climate.STATE_COOL)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_set_target_temp_ac_on(hass, setup_comp_3):
    """Test if target temperature turn ac on."""
    calls = _setup_switch(hass, False)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_temp_change_ac_off_within_tolerance(hass, setup_comp_3):
    """Test if temperature change doesn't turn ac off within tolerance."""
    calls = _setup_switch(hass, True)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    _setup_sensor(hass, 29.8)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_set_temp_change_ac_off_outside_tolerance(hass, setup_comp_3):
    """Test if temperature change turn ac off."""
    calls = _setup_switch(hass, True)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    _setup_sensor(hass, 27)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_temp_change_ac_on_within_tolerance(hass, setup_comp_3):
    """Test if temperature change doesn't turn ac on within tolerance."""
    calls = _setup_switch(hass, False)
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    _setup_sensor(hass, 25.2)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_temp_change_ac_on_outside_tolerance(hass, setup_comp_3):
    """Test if temperature change turn ac on."""
    calls = _setup_switch(hass, False)
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_running_when_operating_mode_is_off_2(hass, setup_comp_3):
    """Test that the switch turns off when enabled is set False."""
    calls = _setup_switch(hass, True)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    common.async_set_operation_mode(hass, STATE_OFF)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_no_state_change_when_operation_mode_off_2(hass, setup_comp_3):
    """Test that the switch doesn't turn on when enabled is False."""
    calls = _setup_switch(hass, False)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    common.async_set_operation_mode(hass, STATE_OFF)
    await hass.async_block_till_done()
    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert 0 == len(calls)


@pytest.fixture
def setup_comp_4(hass):
    """Initialize components."""
    hass.config.temperature_unit = TEMP_CELSIUS
    assert hass.loop.run_until_complete(async_setup_component(
        hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'cold_tolerance': 0.3,
            'hot_tolerance': 0.3,
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'ac_mode': True,
            'min_cycle_duration': datetime.timedelta(minutes=10)
        }}))


async def test_temp_change_ac_trigger_on_not_long_enough(hass, setup_comp_4):
    """Test if temperature change turn ac on."""
    calls = _setup_switch(hass, False)
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_temp_change_ac_trigger_on_long_enough(hass, setup_comp_4):
    """Test if temperature change turn ac on."""
    fake_changed = datetime.datetime(1918, 11, 11, 11, 11, 11,
                                     tzinfo=datetime.timezone.utc)
    with mock.patch('homeassistant.helpers.condition.dt_util.utcnow',
                    return_value=fake_changed):
        calls = _setup_switch(hass, False)
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_temp_change_ac_trigger_off_not_long_enough(hass, setup_comp_4):
    """Test if temperature change turn ac on."""
    calls = _setup_switch(hass, True)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_temp_change_ac_trigger_off_long_enough(hass, setup_comp_4):
    """Test if temperature change turn ac on."""
    fake_changed = datetime.datetime(1918, 11, 11, 11, 11, 11,
                                     tzinfo=datetime.timezone.utc)
    with mock.patch('homeassistant.helpers.condition.dt_util.utcnow',
                    return_value=fake_changed):
        calls = _setup_switch(hass, True)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_mode_change_ac_trigger_off_not_long_enough(hass, setup_comp_4):
    """Test if mode change turns ac off despite minimum cycle."""
    calls = _setup_switch(hass, True)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    common.async_set_operation_mode(hass, climate.STATE_OFF)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert 'homeassistant' == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_mode_change_ac_trigger_on_not_long_enough(hass, setup_comp_4):
    """Test if mode change turns ac on despite minimum cycle."""
    calls = _setup_switch(hass, False)
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    common.async_set_operation_mode(hass, climate.STATE_HEAT)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert 'homeassistant' == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data['entity_id']


@pytest.fixture
def setup_comp_5(hass):
    """Initialize components."""
    hass.config.temperature_unit = TEMP_CELSIUS
    assert hass.loop.run_until_complete(async_setup_component(
        hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'cold_tolerance': 0.3,
            'hot_tolerance': 0.3,
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'ac_mode': True,
            'min_cycle_duration': datetime.timedelta(minutes=10)
        }}))


async def test_temp_change_ac_trigger_on_not_long_enough_2(hass, setup_comp_5):
    """Test if temperature change turn ac on."""
    calls = _setup_switch(hass, False)
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_temp_change_ac_trigger_on_long_enough_2(hass, setup_comp_5):
    """Test if temperature change turn ac on."""
    fake_changed = datetime.datetime(1918, 11, 11, 11, 11, 11,
                                     tzinfo=datetime.timezone.utc)
    with mock.patch('homeassistant.helpers.condition.dt_util.utcnow',
                    return_value=fake_changed):
        calls = _setup_switch(hass, False)
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_temp_change_ac_trigger_off_not_long_enough_2(
        hass, setup_comp_5):
    """Test if temperature change turn ac on."""
    calls = _setup_switch(hass, True)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_temp_change_ac_trigger_off_long_enough_2(hass, setup_comp_5):
    """Test if temperature change turn ac on."""
    fake_changed = datetime.datetime(1918, 11, 11, 11, 11, 11,
                                     tzinfo=datetime.timezone.utc)
    with mock.patch('homeassistant.helpers.condition.dt_util.utcnow',
                    return_value=fake_changed):
        calls = _setup_switch(hass, True)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_mode_change_ac_trigger_off_not_long_enough_2(
        hass, setup_comp_5):
    """Test if mode change turns ac off despite minimum cycle."""
    calls = _setup_switch(hass, True)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    common.async_set_operation_mode(hass, climate.STATE_OFF)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert 'homeassistant' == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_mode_change_ac_trigger_on_not_long_enough_2(hass, setup_comp_5):
    """Test if mode change turns ac on despite minimum cycle."""
    calls = _setup_switch(hass, False)
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    common.async_set_operation_mode(hass, climate.STATE_HEAT)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert 'homeassistant' == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data['entity_id']


@pytest.fixture
def setup_comp_6(hass):
    """Initialize components."""
    hass.config.temperature_unit = TEMP_CELSIUS
    assert hass.loop.run_until_complete(async_setup_component(
        hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'cold_tolerance': 0.3,
            'hot_tolerance': 0.3,
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'min_cycle_duration': datetime.timedelta(minutes=10)
        }}))


async def test_temp_change_heater_trigger_off_not_long_enough(
        hass, setup_comp_6):
    """Test if temp change doesn't turn heater off because of time."""
    calls = _setup_switch(hass, True)
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_temp_change_heater_trigger_on_not_long_enough(
        hass, setup_comp_6):
    """Test if temp change doesn't turn heater on because of time."""
    calls = _setup_switch(hass, False)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_temp_change_heater_trigger_on_long_enough(hass, setup_comp_6):
    """Test if temperature change turn heater on after min cycle."""
    fake_changed = datetime.datetime(1918, 11, 11, 11, 11, 11,
                                     tzinfo=datetime.timezone.utc)
    with mock.patch('homeassistant.helpers.condition.dt_util.utcnow',
                    return_value=fake_changed):
        calls = _setup_switch(hass, False)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_temp_change_heater_trigger_off_long_enough(hass, setup_comp_6):
    """Test if temperature change turn heater off after min cycle."""
    fake_changed = datetime.datetime(1918, 11, 11, 11, 11, 11,
                                     tzinfo=datetime.timezone.utc)
    with mock.patch('homeassistant.helpers.condition.dt_util.utcnow',
                    return_value=fake_changed):
        calls = _setup_switch(hass, True)
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_mode_change_heater_trigger_off_not_long_enough(
        hass, setup_comp_6):
    """Test if mode change turns heater off despite minimum cycle."""
    calls = _setup_switch(hass, True)
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    common.async_set_operation_mode(hass, climate.STATE_OFF)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert 'homeassistant' == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_mode_change_heater_trigger_on_not_long_enough(
        hass, setup_comp_6):
    """Test if mode change turns heater on despite minimum cycle."""
    calls = _setup_switch(hass, False)
    common.async_set_temperature(hass, 30)
    await hass.async_block_till_done()
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    common.async_set_operation_mode(hass, climate.STATE_HEAT)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert 'homeassistant' == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data['entity_id']


@pytest.fixture
def setup_comp_7(hass):
    """Initialize components."""
    hass.config.temperature_unit = TEMP_CELSIUS
    assert hass.loop.run_until_complete(async_setup_component(
        hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'cold_tolerance': 0.3,
            'hot_tolerance': 0.3,
            'heater': ENT_SWITCH,
            'target_temp': 25,
            'target_sensor': ENT_SENSOR,
            'ac_mode': True,
            'min_cycle_duration': datetime.timedelta(minutes=15),
            'keep_alive': datetime.timedelta(minutes=10)
        }}))


async def test_temp_change_ac_trigger_on_long_enough_3(hass, setup_comp_7):
    """Test if turn on signal is sent at keep-alive intervals."""
    calls = _setup_switch(hass, True)
    await hass.async_block_till_done()
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    test_time = datetime.datetime.now(pytz.UTC)
    _send_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    _send_time_changed(hass, test_time + datetime.timedelta(minutes=5))
    await hass.async_block_till_done()
    assert 0 == len(calls)
    _send_time_changed(hass, test_time + datetime.timedelta(minutes=10))
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_temp_change_ac_trigger_off_long_enough_3(hass, setup_comp_7):
    """Test if turn on signal is sent at keep-alive intervals."""
    calls = _setup_switch(hass, False)
    await hass.async_block_till_done()
    _setup_sensor(hass, 20)
    await hass.async_block_till_done()
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    test_time = datetime.datetime.now(pytz.UTC)
    _send_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    _send_time_changed(hass, test_time + datetime.timedelta(minutes=5))
    await hass.async_block_till_done()
    assert 0 == len(calls)
    _send_time_changed(hass, test_time + datetime.timedelta(minutes=10))
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data['entity_id']


def _send_time_changed(hass, now):
    """Send a time changed event."""
    hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: now})


@pytest.fixture
def setup_comp_8(hass):
    """Initialize components."""
    hass.config.temperature_unit = TEMP_CELSIUS
    assert hass.loop.run_until_complete(async_setup_component(
        hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'cold_tolerance': 0.3,
            'hot_tolerance': 0.3,
            'target_temp': 25,
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'min_cycle_duration': datetime.timedelta(minutes=15),
            'keep_alive': datetime.timedelta(minutes=10)
        }}))


async def test_temp_change_heater_trigger_on_long_enough_2(hass, setup_comp_8):
    """Test if turn on signal is sent at keep-alive intervals."""
    calls = _setup_switch(hass, True)
    await hass.async_block_till_done()
    _setup_sensor(hass, 20)
    await hass.async_block_till_done()
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    test_time = datetime.datetime.now(pytz.UTC)
    _send_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    _send_time_changed(hass, test_time + datetime.timedelta(minutes=5))
    await hass.async_block_till_done()
    assert 0 == len(calls)
    _send_time_changed(hass, test_time + datetime.timedelta(minutes=10))
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data['entity_id']


async def test_temp_change_heater_trigger_off_long_enough_2(
        hass, setup_comp_8):
    """Test if turn on signal is sent at keep-alive intervals."""
    calls = _setup_switch(hass, False)
    await hass.async_block_till_done()
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    common.async_set_temperature(hass, 25)
    await hass.async_block_till_done()
    test_time = datetime.datetime.now(pytz.UTC)
    _send_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    _send_time_changed(hass, test_time + datetime.timedelta(minutes=5))
    await hass.async_block_till_done()
    assert 0 == len(calls)
    _send_time_changed(hass, test_time + datetime.timedelta(minutes=10))
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data['entity_id']


@pytest.fixture
def setup_comp_9(hass):
    """Initialize components."""
    hass.config.temperature_unit = TEMP_CELSIUS
    assert hass.loop.run_until_complete(async_setup_component(
        hass, climate.DOMAIN, {'climate': [
            {
                'platform': 'generic_thermostat',
                'name': 'test_heat',
                'heater': ENT_SWITCH,
                'target_sensor': ENT_SENSOR
            },
            {
                'platform': 'generic_thermostat',
                'name': 'test_cool',
                'heater': ENT_SWITCH,
                'ac_mode': True,
                'target_sensor': ENT_SENSOR
            }
        ]}))


async def test_turn_on_when_off(hass, setup_comp_9):
    """Test if climate.turn_on turns on a turned off device."""
    common.async_set_operation_mode(hass, STATE_OFF)
    await hass.async_block_till_done()
    await hass.services.async_call('climate', SERVICE_TURN_ON)
    await hass.async_block_till_done()
    state_heat = hass.states.get(HEAT_ENTITY)
    state_cool = hass.states.get(COOL_ENTITY)
    assert STATE_HEAT == \
        state_heat.attributes.get('operation_mode')
    assert STATE_COOL == \
        state_cool.attributes.get('operation_mode')


async def test_turn_on_when_on(hass, setup_comp_9):
    """Test if climate.turn_on does nothing to a turned on device."""
    common.async_set_operation_mode(hass, STATE_HEAT, HEAT_ENTITY)
    common.async_set_operation_mode(hass, STATE_COOL, COOL_ENTITY)
    await hass.async_block_till_done()
    await hass.services.async_call('climate', SERVICE_TURN_ON)
    await hass.async_block_till_done()
    state_heat = hass.states.get(HEAT_ENTITY)
    state_cool = hass.states.get(COOL_ENTITY)
    assert STATE_HEAT == \
        state_heat.attributes.get('operation_mode')
    assert STATE_COOL == \
        state_cool.attributes.get('operation_mode')


async def test_turn_off_when_on(hass, setup_comp_9):
    """Test if climate.turn_off turns off a turned on device."""
    common.async_set_operation_mode(hass, STATE_HEAT, HEAT_ENTITY)
    common.async_set_operation_mode(hass, STATE_COOL, COOL_ENTITY)
    await hass.async_block_till_done()
    await hass.services.async_call('climate', SERVICE_TURN_OFF)
    await hass.async_block_till_done()
    state_heat = hass.states.get(HEAT_ENTITY)
    state_cool = hass.states.get(COOL_ENTITY)
    assert STATE_OFF == \
        state_heat.attributes.get('operation_mode')
    assert STATE_OFF == \
        state_cool.attributes.get('operation_mode')


async def test_turn_off_when_off(hass, setup_comp_9):
    """Test if climate.turn_off does nothing to a turned off device."""
    common.async_set_operation_mode(hass, STATE_OFF)
    await hass.async_block_till_done()
    await hass.services.async_call('climate', SERVICE_TURN_OFF)
    await hass.async_block_till_done()
    state_heat = hass.states.get(HEAT_ENTITY)
    state_cool = hass.states.get(COOL_ENTITY)
    assert STATE_OFF == \
        state_heat.attributes.get('operation_mode')
    assert STATE_OFF == \
        state_cool.attributes.get('operation_mode')


@pytest.fixture
def setup_comp_10(hass):
    """Initialize components."""
    hass.config.temperature_unit = TEMP_FAHRENHEIT
    assert hass.loop.run_until_complete(async_setup_component(
        hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'cold_tolerance': 0.3,
            'hot_tolerance': 0.3,
            'target_temp': 25,
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'min_cycle_duration': datetime.timedelta(minutes=15),
            'keep_alive': datetime.timedelta(minutes=10),
            'precision': 0.1
        }}))


async def test_precision(hass, setup_comp_10):
    """Test that setting precision to tenths works as intended."""
    common.async_set_operation_mode(hass, STATE_OFF)
    await hass.async_block_till_done()
    await hass.services.async_call('climate', SERVICE_TURN_OFF)
    await hass.async_block_till_done()
    common.async_set_temperature(hass, 23.27)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert 23.3 == state.attributes.get('temperature')


async def test_custom_setup_params(hass):
    """Test the setup with custom parameters."""
    result = await async_setup_component(
        hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'min_temp': MIN_TEMP,
            'max_temp': MAX_TEMP,
            'target_temp': TARGET_TEMP
        }})
    assert result
    state = hass.states.get(ENTITY)
    assert state.attributes.get('min_temp') == MIN_TEMP
    assert state.attributes.get('max_temp') == MAX_TEMP
    assert state.attributes.get('temperature') == TARGET_TEMP


async def test_restore_state(hass):
    """Ensure states are restored on startup."""
    mock_restore_cache(hass, (
        State('climate.test_thermostat', '0', {ATTR_TEMPERATURE: "20",
              climate.ATTR_OPERATION_MODE: "off", ATTR_AWAY_MODE: "on"}),
    ))

    hass.state = CoreState.starting

    await async_setup_component(
        hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test_thermostat',
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
        }})

    state = hass.states.get('climate.test_thermostat')
    assert(state.attributes[ATTR_TEMPERATURE] == 20)
    assert(state.attributes[climate.ATTR_OPERATION_MODE] == "off")
    assert(state.state == STATE_OFF)


async def test_no_restore_state(hass):
    """Ensure states are restored on startup if they exist.

    Allows for graceful reboot.
    """
    mock_restore_cache(hass, (
        State('climate.test_thermostat', '0', {ATTR_TEMPERATURE: "20",
              climate.ATTR_OPERATION_MODE: "off", ATTR_AWAY_MODE: "on"}),
    ))

    hass.state = CoreState.starting

    await async_setup_component(
        hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test_thermostat',
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'target_temp': 22
        }})

    state = hass.states.get('climate.test_thermostat')
    assert(state.attributes[ATTR_TEMPERATURE] == 22)
    assert(state.state == STATE_OFF)


async def test_restore_state_uncoherence_case(hass):
    """
    Test restore from a strange state.

    - Turn the generic thermostat off
    - Restart HA and restore state from DB
    """
    _mock_restore_cache(hass, temperature=20)

    calls = _setup_switch(hass, False)
    _setup_sensor(hass, 15)
    await _setup_climate(hass, )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY)
    assert 20 == state.attributes[ATTR_TEMPERATURE]
    assert STATE_OFF == \
        state.attributes[climate.ATTR_OPERATION_MODE]
    assert STATE_OFF == state.state
    assert 0 == len(calls)

    calls = _setup_switch(hass, False)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert STATE_OFF == \
        state.attributes[climate.ATTR_OPERATION_MODE]
    assert STATE_OFF == state.state


async def _setup_climate(hass):
    assert await async_setup_component(hass, climate.DOMAIN, {'climate': {
        'platform': 'generic_thermostat',
        'name': 'test',
        'cold_tolerance': 2,
        'hot_tolerance': 4,
        'away_temp': 30,
        'heater': ENT_SWITCH,
        'target_sensor': ENT_SENSOR,
        'ac_mode': True
    }})


def _mock_restore_cache(hass, temperature=20, operation_mode=STATE_OFF):
    mock_restore_cache(hass, (
        State(ENTITY, '0', {
            ATTR_TEMPERATURE: str(temperature),
            climate.ATTR_OPERATION_MODE: operation_mode,
            ATTR_AWAY_MODE: "on"}),
    ))
