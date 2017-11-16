"""The tests for the generic_thermostat."""
import asyncio
import datetime
import unittest
from unittest import mock
import pytz

import homeassistant.core as ha
from homeassistant.core import callback
from homeassistant.setup import setup_component, async_setup_component
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_OFF,
    TEMP_CELSIUS,
)
from homeassistant.util.unit_system import METRIC_SYSTEM
from homeassistant.components import climate

from tests.common import assert_setup_component, get_test_home_assistant


ENTITY = 'climate.test'
ENT_SENSOR = 'sensor.test'
ENT_SWITCH = 'switch.test'
MIN_TEMP = 3.0
MAX_TEMP = 65.0
TARGET_TEMP = 42.0
COLD_TOLERANCE = 0.5
HOT_TOLERANCE = 0.5


class TestSetupClimateGenericThermostat(unittest.TestCase):
    """Test the Generic thermostat with custom config."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_missing_conf(self):
        """Test set up heat_control with missing config values."""
        config = {
            'name': 'test',
            'target_sensor': ENT_SENSOR
        }
        with assert_setup_component(0):
            setup_component(self.hass, 'climate', {
                'climate': config})

    def test_valid_conf(self):
        """Test set up generic_thermostat with valid config values."""
        self.assertTrue(
            setup_component(self.hass, 'climate',
                            {'climate': {
                                'platform': 'generic_thermostat',
                                'name': 'test',
                                'heater': ENT_SWITCH,
                                'target_sensor': ENT_SENSOR
                                }})
        )

    def test_setup_with_sensor(self):
        """Test set up heat_control with sensor to trigger update at init."""
        self.hass.states.set(ENT_SENSOR, 22.0, {
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS
        })
        assert setup_component(self.hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR
        }})
        state = self.hass.states.get(ENTITY)
        self.assertEqual(
            TEMP_CELSIUS, state.attributes.get('unit_of_measurement'))
        self.assertEqual(22.0, state.attributes.get('current_temperature'))


class TestClimateGenericThermostat(unittest.TestCase):
    """Test the Generic thermostat."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        assert setup_component(self.hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'cold_tolerance': 2,
            'hot_tolerance': 4,
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR
        }})

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_defaults_to_unknown(self):
        """Test the setting of defaults to unknown."""
        self.assertEqual('idle', self.hass.states.get(ENTITY).state)

    def test_default_setup_params(self):
        """Test the setup with default parameters."""
        state = self.hass.states.get(ENTITY)
        self.assertEqual(7, state.attributes.get('min_temp'))
        self.assertEqual(35, state.attributes.get('max_temp'))
        self.assertEqual(None, state.attributes.get('temperature'))

    def test_get_operation_modes(self):
        """Test that the operation list returns the correct modes."""
        state = self.hass.states.get(ENTITY)
        modes = state.attributes.get('operation_list')
        self.assertEqual([climate.STATE_AUTO, STATE_OFF], modes)

    def test_set_target_temp(self):
        """Test the setting of the target temperature."""
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY)
        self.assertEqual(30.0, state.attributes.get('temperature'))

    def test_sensor_bad_unit(self):
        """Test sensor that have bad unit."""
        state = self.hass.states.get(ENTITY)
        temp = state.attributes.get('current_temperature')
        unit = state.attributes.get('unit_of_measurement')

        self._setup_sensor(22.0, unit='bad_unit')
        self.hass.block_till_done()

        state = self.hass.states.get(ENTITY)
        self.assertEqual(unit, state.attributes.get('unit_of_measurement'))
        self.assertEqual(temp, state.attributes.get('current_temperature'))

    def test_sensor_bad_value(self):
        """Test sensor that have None as state."""
        state = self.hass.states.get(ENTITY)
        temp = state.attributes.get('current_temperature')
        unit = state.attributes.get('unit_of_measurement')

        self._setup_sensor(None)
        self.hass.block_till_done()

        state = self.hass.states.get(ENTITY)
        self.assertEqual(unit, state.attributes.get('unit_of_measurement'))
        self.assertEqual(temp, state.attributes.get('current_temperature'))

    def test_set_target_temp_heater_on(self):
        """Test if target temperature turn heater on."""
        self._setup_switch(False)
        self._setup_sensor(25)
        self.hass.block_till_done()
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_ON, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_set_target_temp_heater_off(self):
        """Test if target temperature turn heater off."""
        self._setup_switch(True)
        self._setup_sensor(30)
        self.hass.block_till_done()
        climate.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_temp_change_heater_on_within_tolerance(self):
        """Test if temperature change doesn't turn on within tolerance."""
        self._setup_switch(False)
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        self._setup_sensor(29)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_temp_change_heater_on_outside_tolerance(self):
        """Test if temperature change turn heater on outside cold tolerance."""
        self._setup_switch(False)
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        self._setup_sensor(27)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_ON, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_temp_change_heater_off_within_tolerance(self):
        """Test if temperature change doesn't turn off within tolerance."""
        self._setup_switch(True)
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        self._setup_sensor(33)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_temp_change_heater_off_outside_tolerance(self):
        """Test if temperature change turn heater off outside hot tolerance."""
        self._setup_switch(True)
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        self._setup_sensor(35)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_running_when_operating_mode_is_off(self):
        """Test that the switch turns off when enabled is set False."""
        self._setup_switch(True)
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        climate.set_operation_mode(self.hass, STATE_OFF)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_no_state_change_when_operation_mode_off(self):
        """Test that the switch doesn't turn on when enabled is False."""
        self._setup_switch(False)
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        climate.set_operation_mode(self.hass, STATE_OFF)
        self.hass.block_till_done()
        self._setup_sensor(25)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    @mock.patch('logging.Logger.error')
    def test_invalid_operating_mode(self, log_mock):
        """Test error handling for invalid operation mode."""
        climate.set_operation_mode(self.hass, 'invalid mode')
        self.hass.block_till_done()
        self.assertEqual(log_mock.call_count, 1)

    def test_operating_mode_auto(self):
        """Test change mode from OFF to AUTO.

        Switch turns on when temp below setpoint and mode changes.
        """
        climate.set_operation_mode(self.hass, STATE_OFF)
        climate.set_temperature(self.hass, 30)
        self._setup_sensor(25)
        self.hass.block_till_done()
        self._setup_switch(False)
        climate.set_operation_mode(self.hass, climate.STATE_AUTO)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_ON, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def _setup_sensor(self, temp, unit=TEMP_CELSIUS):
        """Setup the test sensor."""
        self.hass.states.set(ENT_SENSOR, temp, {
            ATTR_UNIT_OF_MEASUREMENT: unit
        })

    def _setup_switch(self, is_on):
        """Setup the test switch."""
        self.hass.states.set(ENT_SWITCH, STATE_ON if is_on else STATE_OFF)
        self.calls = []

        @callback
        def log_call(call):
            """Log service calls."""
            self.calls.append(call)

        self.hass.services.register('switch', SERVICE_TURN_ON, log_call)
        self.hass.services.register('switch', SERVICE_TURN_OFF, log_call)


class TestClimateGenericThermostatACMode(unittest.TestCase):
    """Test the Generic thermostat."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.temperature_unit = TEMP_CELSIUS
        assert setup_component(self.hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'cold_tolerance': 2,
            'hot_tolerance': 4,
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'ac_mode': True
        }})

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_set_target_temp_ac_off(self):
        """Test if target temperature turn ac off."""
        self._setup_switch(True)
        self._setup_sensor(25)
        self.hass.block_till_done()
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_set_target_temp_ac_on(self):
        """Test if target temperature turn ac on."""
        self._setup_switch(False)
        self._setup_sensor(30)
        self.hass.block_till_done()
        climate.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_ON, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_temp_change_ac_off_within_tolerance(self):
        """Test if temperature change doesn't turn ac off within tolerance."""
        self._setup_switch(True)
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        self._setup_sensor(29.8)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_set_temp_change_ac_off_outside_tolerance(self):
        """Test if temperature change turn ac off."""
        self._setup_switch(True)
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        self._setup_sensor(27)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_temp_change_ac_on_within_tolerance(self):
        """Test if temperature change doesn't turn ac on within tolerance."""
        self._setup_switch(False)
        climate.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        self._setup_sensor(25.2)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_temp_change_ac_on_outside_tolerance(self):
        """Test if temperature change turn ac on."""
        self._setup_switch(False)
        climate.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        self._setup_sensor(30)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_ON, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_running_when_operating_mode_is_off(self):
        """Test that the switch turns off when enabled is set False."""
        self._setup_switch(True)
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        climate.set_operation_mode(self.hass, STATE_OFF)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_no_state_change_when_operation_mode_off(self):
        """Test that the switch doesn't turn on when enabled is False."""
        self._setup_switch(False)
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        climate.set_operation_mode(self.hass, STATE_OFF)
        self.hass.block_till_done()
        self._setup_sensor(35)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def _setup_sensor(self, temp, unit=TEMP_CELSIUS):
        """Setup the test sensor."""
        self.hass.states.set(ENT_SENSOR, temp, {
            ATTR_UNIT_OF_MEASUREMENT: unit
        })

    def _setup_switch(self, is_on):
        """Setup the test switch."""
        self.hass.states.set(ENT_SWITCH, STATE_ON if is_on else STATE_OFF)
        self.calls = []

        @callback
        def log_call(call):
            """Log service calls."""
            self.calls.append(call)

        self.hass.services.register('switch', SERVICE_TURN_ON, log_call)
        self.hass.services.register('switch', SERVICE_TURN_OFF, log_call)


class TestClimateGenericThermostatACModeMinCycle(unittest.TestCase):
    """Test the Generic Thermostat."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.temperature_unit = TEMP_CELSIUS
        assert setup_component(self.hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'cold_tolerance': 0.3,
            'hot_tolerance': 0.3,
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'ac_mode': True,
            'min_cycle_duration': datetime.timedelta(minutes=10)
        }})

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_temp_change_ac_trigger_on_not_long_enough(self):
        """Test if temperature change turn ac on."""
        self._setup_switch(False)
        climate.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        self._setup_sensor(30)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_temp_change_ac_trigger_on_long_enough(self):
        """Test if temperature change turn ac on."""
        fake_changed = datetime.datetime(1918, 11, 11, 11, 11, 11,
                                         tzinfo=datetime.timezone.utc)
        with mock.patch('homeassistant.helpers.condition.dt_util.utcnow',
                        return_value=fake_changed):
            self._setup_switch(False)
        climate.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        self._setup_sensor(30)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_ON, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_temp_change_ac_trigger_off_not_long_enough(self):
        """Test if temperature change turn ac on."""
        self._setup_switch(True)
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        self._setup_sensor(25)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_temp_change_ac_trigger_off_long_enough(self):
        """Test if temperature change turn ac on."""
        fake_changed = datetime.datetime(1918, 11, 11, 11, 11, 11,
                                         tzinfo=datetime.timezone.utc)
        with mock.patch('homeassistant.helpers.condition.dt_util.utcnow',
                        return_value=fake_changed):
            self._setup_switch(True)
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        self._setup_sensor(25)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def _setup_sensor(self, temp, unit=TEMP_CELSIUS):
        """Setup the test sensor."""
        self.hass.states.set(ENT_SENSOR, temp, {
            ATTR_UNIT_OF_MEASUREMENT: unit
        })

    def _setup_switch(self, is_on):
        """Setup the test switch."""
        self.hass.states.set(ENT_SWITCH, STATE_ON if is_on else STATE_OFF)
        self.calls = []

        @callback
        def log_call(call):
            """Log service calls."""
            self.calls.append(call)

        self.hass.services.register('switch', SERVICE_TURN_ON, log_call)
        self.hass.services.register('switch', SERVICE_TURN_OFF, log_call)


class TestClimateGenericThermostatMinCycle(unittest.TestCase):
    """Test the Generic thermostat."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.temperature_unit = TEMP_CELSIUS
        assert setup_component(self.hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'cold_tolerance': 0.3,
            'hot_tolerance': 0.3,
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'min_cycle_duration': datetime.timedelta(minutes=10)
        }})

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_temp_change_heater_trigger_off_not_long_enough(self):
        """Test if temp change doesn't turn heater off because of time."""
        self._setup_switch(True)
        climate.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        self._setup_sensor(30)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_temp_change_heater_trigger_on_not_long_enough(self):
        """Test if temp change doesn't turn heater on because of time."""
        self._setup_switch(False)
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        self._setup_sensor(25)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_temp_change_heater_trigger_on_long_enough(self):
        """Test if temperature change turn heater on after min cycle."""
        fake_changed = datetime.datetime(1918, 11, 11, 11, 11, 11,
                                         tzinfo=datetime.timezone.utc)
        with mock.patch('homeassistant.helpers.condition.dt_util.utcnow',
                        return_value=fake_changed):
            self._setup_switch(False)
        climate.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        self._setup_sensor(25)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_ON, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_temp_change_heater_trigger_off_long_enough(self):
        """Test if temperature change turn heater off after min cycle."""
        fake_changed = datetime.datetime(1918, 11, 11, 11, 11, 11,
                                         tzinfo=datetime.timezone.utc)
        with mock.patch('homeassistant.helpers.condition.dt_util.utcnow',
                        return_value=fake_changed):
            self._setup_switch(True)
        climate.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        self._setup_sensor(30)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def _setup_sensor(self, temp, unit=TEMP_CELSIUS):
        """Setup the test sensor."""
        self.hass.states.set(ENT_SENSOR, temp, {
            ATTR_UNIT_OF_MEASUREMENT: unit
        })

    def _setup_switch(self, is_on):
        """Setup the test switch."""
        self.hass.states.set(ENT_SWITCH, STATE_ON if is_on else STATE_OFF)
        self.calls = []

        @callback
        def log_call(call):
            """Log service calls."""
            self.calls.append(call)

        self.hass.services.register('switch', SERVICE_TURN_ON, log_call)
        self.hass.services.register('switch', SERVICE_TURN_OFF, log_call)


class TestClimateGenericThermostatACKeepAlive(unittest.TestCase):
    """Test the Generic Thermostat."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.temperature_unit = TEMP_CELSIUS
        assert setup_component(self.hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'cold_tolerance': 0.3,
            'hot_tolerance': 0.3,
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'ac_mode': True,
            'keep_alive': datetime.timedelta(minutes=10)
        }})

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_temp_change_ac_trigger_on_long_enough(self):
        """Test if turn on signal is sent at keep-alive intervals."""
        self._setup_switch(True)
        self.hass.block_till_done()
        self._setup_sensor(30)
        self.hass.block_till_done()
        climate.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        test_time = datetime.datetime.now(pytz.UTC)
        self._send_time_changed(test_time)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))
        self._send_time_changed(test_time + datetime.timedelta(minutes=5))
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))
        self._send_time_changed(test_time + datetime.timedelta(minutes=10))
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_ON, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_temp_change_ac_trigger_off_long_enough(self):
        """Test if turn on signal is sent at keep-alive intervals."""
        self._setup_switch(False)
        self.hass.block_till_done()
        self._setup_sensor(20)
        self.hass.block_till_done()
        climate.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        test_time = datetime.datetime.now(pytz.UTC)
        self._send_time_changed(test_time)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))
        self._send_time_changed(test_time + datetime.timedelta(minutes=5))
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))
        self._send_time_changed(test_time + datetime.timedelta(minutes=10))
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def _send_time_changed(self, now):
        """Send a time changed event."""
        self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: now})

    def _setup_sensor(self, temp, unit=TEMP_CELSIUS):
        """Setup the test sensor."""
        self.hass.states.set(ENT_SENSOR, temp, {
            ATTR_UNIT_OF_MEASUREMENT: unit
        })

    def _setup_switch(self, is_on):
        """Setup the test switch."""
        self.hass.states.set(ENT_SWITCH, STATE_ON if is_on else STATE_OFF)
        self.calls = []

        @callback
        def log_call(call):
            """Log service calls."""
            self.calls.append(call)

        self.hass.services.register('switch', SERVICE_TURN_ON, log_call)
        self.hass.services.register('switch', SERVICE_TURN_OFF, log_call)


class TestClimateGenericThermostatKeepAlive(unittest.TestCase):
    """Test the Generic Thermostat."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.temperature_unit = TEMP_CELSIUS
        assert setup_component(self.hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'cold_tolerance': 0.3,
            'hot_tolerance': 0.3,
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'keep_alive': datetime.timedelta(minutes=10)
        }})

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_temp_change_heater_trigger_on_long_enough(self):
        """Test if turn on signal is sent at keep-alive intervals."""
        self._setup_switch(True)
        self.hass.block_till_done()
        self._setup_sensor(20)
        self.hass.block_till_done()
        climate.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        test_time = datetime.datetime.now(pytz.UTC)
        self._send_time_changed(test_time)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))
        self._send_time_changed(test_time + datetime.timedelta(minutes=5))
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))
        self._send_time_changed(test_time + datetime.timedelta(minutes=10))
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_ON, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_temp_change_heater_trigger_off_long_enough(self):
        """Test if turn on signal is sent at keep-alive intervals."""
        self._setup_switch(False)
        self.hass.block_till_done()
        self._setup_sensor(30)
        self.hass.block_till_done()
        climate.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        test_time = datetime.datetime.now(pytz.UTC)
        self._send_time_changed(test_time)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))
        self._send_time_changed(test_time + datetime.timedelta(minutes=5))
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))
        self._send_time_changed(test_time + datetime.timedelta(minutes=10))
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def _send_time_changed(self, now):
        """Send a time changed event."""
        self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: now})

    def _setup_sensor(self, temp, unit=TEMP_CELSIUS):
        """Setup the test sensor."""
        self.hass.states.set(ENT_SENSOR, temp, {
            ATTR_UNIT_OF_MEASUREMENT: unit
        })

    def _setup_switch(self, is_on):
        """Setup the test switch."""
        self.hass.states.set(ENT_SWITCH, STATE_ON if is_on else STATE_OFF)
        self.calls = []

        @callback
        def log_call(call):
            """Log service calls."""
            self.calls.append(call)

        self.hass.services.register('switch', SERVICE_TURN_ON, log_call)
        self.hass.services.register('switch', SERVICE_TURN_OFF, log_call)


@asyncio.coroutine
def test_custom_setup_params(hass):
    """Test the setup with custom parameters."""
    result = yield from async_setup_component(
        hass, climate.DOMAIN, {'climate': {
            'platform': 'generic_thermostat',
            'name': 'test',
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'min_temp': MIN_TEMP,
            'max_temp': MAX_TEMP,
            'target_temp': TARGET_TEMP,
        }})
    assert result
    state = hass.states.get(ENTITY)
    assert state.attributes.get('min_temp') == MIN_TEMP
    assert state.attributes.get('max_temp') == MAX_TEMP
    assert state.attributes.get('temperature') == TARGET_TEMP
