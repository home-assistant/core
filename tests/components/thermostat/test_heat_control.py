"""The tests for the heat control thermostat."""
import datetime
import unittest
from unittest import mock


from homeassistant.bootstrap import _setup_component
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_OFF,
    TEMP_CELSIUS,
)
from homeassistant.util.unit_system import METRIC_SYSTEM
from homeassistant.components import thermostat

from tests.common import get_test_home_assistant


ENTITY = 'thermostat.test'
ENT_SENSOR = 'sensor.test'
ENT_SWITCH = 'switch.test'
MIN_TEMP = 3.0
MAX_TEMP = 65.0
TARGET_TEMP = 42.0


class TestSetupThermostatHeatControl(unittest.TestCase):
    """Test the Heat Control thermostat with custom config."""

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
        self.assertFalse(_setup_component(self.hass, 'thermostat', {
            'thermostat': config}))

    def test_valid_conf(self):
        """Test set up heat_control with valid config values."""
        self.assertTrue(_setup_component(self.hass, 'thermostat',
                        {'thermostat': {
                            'platform': 'heat_control',
                            'name': 'test',
                            'heater': ENT_SWITCH,
                            'target_sensor': ENT_SENSOR}}))

    def test_setup_with_sensor(self):
        """Test set up heat_control with sensor to trigger update at init."""
        self.hass.states.set(ENT_SENSOR, 22.0, {
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS
        })
        thermostat.setup(self.hass, {'thermostat': {
            'platform': 'heat_control',
            'name': 'test',
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR
        }})
        state = self.hass.states.get(ENTITY)
        self.assertEqual(
            TEMP_CELSIUS, state.attributes.get('unit_of_measurement'))
        self.assertEqual(22.0, state.attributes.get('current_temperature'))


class TestThermostatHeatControl(unittest.TestCase):
    """Test the Heat Control thermostat."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        thermostat.setup(self.hass, {'thermostat': {
            'platform': 'heat_control',
            'name': 'test',
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR
        }})

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_defaults_to_unknown(self):
        """Test the setting of defaults to unknown."""
        self.assertEqual('unknown', self.hass.states.get(ENTITY).state)

    def test_default_setup_params(self):
        """Test the setup with default parameters."""
        state = self.hass.states.get(ENTITY)
        self.assertEqual(7, state.attributes.get('min_temp'))
        self.assertEqual(35, state.attributes.get('max_temp'))
        self.assertEqual(None, state.attributes.get('temperature'))

    def test_custom_setup_params(self):
        """Test the setup with custom parameters."""
        thermostat.setup(self.hass, {'thermostat': {
            'platform': 'heat_control',
            'name': 'test',
            'heater': ENT_SWITCH,
            'target_sensor': ENT_SENSOR,
            'min_temp': MIN_TEMP,
            'max_temp': MAX_TEMP,
            'target_temp': TARGET_TEMP
        }})
        state = self.hass.states.get(ENTITY)
        self.assertEqual(MIN_TEMP, state.attributes.get('min_temp'))
        self.assertEqual(MAX_TEMP, state.attributes.get('max_temp'))
        self.assertEqual(TARGET_TEMP, state.attributes.get('temperature'))
        self.assertEqual(str(TARGET_TEMP), self.hass.states.get(ENTITY).state)

    def test_set_target_temp(self):
        """Test the setting of the target temperature."""
        thermostat.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        self.assertEqual('30.0', self.hass.states.get(ENTITY).state)

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
        thermostat.set_temperature(self.hass, 30)
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
        thermostat.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_set_temp_change_heater_on(self):
        """Test if temperature change turn heater on."""
        self._setup_switch(False)
        thermostat.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        self._setup_sensor(25)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_ON, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_temp_change_heater_off(self):
        """Test if temperature change turn heater off."""
        self._setup_switch(True)
        thermostat.set_temperature(self.hass, 25)
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

        def log_call(call):
            """Log service calls."""
            self.calls.append(call)

        self.hass.services.register('switch', SERVICE_TURN_ON, log_call)
        self.hass.services.register('switch', SERVICE_TURN_OFF, log_call)


class TestThermostatHeatControlACMode(unittest.TestCase):
    """Test the Heat Control thermostat."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.temperature_unit = TEMP_CELSIUS
        thermostat.setup(self.hass, {'thermostat': {
            'platform': 'heat_control',
            'name': 'test',
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
        thermostat.set_temperature(self.hass, 30)
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
        thermostat.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_ON, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_set_temp_change_ac_off(self):
        """Test if temperature change turn ac off."""
        self._setup_switch(True)
        thermostat.set_temperature(self.hass, 30)
        self.hass.block_till_done()
        self._setup_sensor(25)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual(ENT_SWITCH, call.data['entity_id'])

    def test_temp_change_ac_on(self):
        """Test if temperature change turn ac on."""
        self._setup_switch(False)
        thermostat.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        self._setup_sensor(30)
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

        def log_call(call):
            """Log service calls."""
            self.calls.append(call)

        self.hass.services.register('switch', SERVICE_TURN_ON, log_call)
        self.hass.services.register('switch', SERVICE_TURN_OFF, log_call)


class TestThermostatHeatControlACModeMinCycle(unittest.TestCase):
    """Test the Heat Control thermostat."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.temperature_unit = TEMP_CELSIUS
        thermostat.setup(self.hass, {'thermostat': {
            'platform': 'heat_control',
            'name': 'test',
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
        thermostat.set_temperature(self.hass, 25)
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
        thermostat.set_temperature(self.hass, 25)
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
        thermostat.set_temperature(self.hass, 30)
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
        thermostat.set_temperature(self.hass, 30)
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

        def log_call(call):
            """Log service calls."""
            self.calls.append(call)

        self.hass.services.register('switch', SERVICE_TURN_ON, log_call)
        self.hass.services.register('switch', SERVICE_TURN_OFF, log_call)


class TestThermostatHeatControlMinCycle(unittest.TestCase):
    """Test the Heat Control thermostat."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.temperature_unit = TEMP_CELSIUS
        thermostat.setup(self.hass, {'thermostat': {
            'platform': 'heat_control',
            'name': 'test',
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
        thermostat.set_temperature(self.hass, 25)
        self.hass.block_till_done()
        self._setup_sensor(30)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_temp_change_heater_trigger_on_not_long_enough(self):
        """Test if temp change doesn't turn heater on because of time."""
        self._setup_switch(False)
        thermostat.set_temperature(self.hass, 30)
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
        thermostat.set_temperature(self.hass, 30)
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
        thermostat.set_temperature(self.hass, 25)
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

        def log_call(call):
            """Log service calls."""
            self.calls.append(call)

        self.hass.services.register('switch', SERVICE_TURN_ON, log_call)
        self.hass.services.register('switch', SERVICE_TURN_OFF, log_call)
