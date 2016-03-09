"""The tests for the heat control thermostat."""
import unittest

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_OFF,
    TEMP_CELCIUS,
)
from homeassistant.components import thermostat

from tests.common import get_test_home_assistant


entity = 'thermostat.test'
ent_sensor = 'sensor.test'
ent_switch = 'switch.test'
min_temp = 3.0
max_temp = 65.0
target_temp = 42.0


class TestThermostatHeatControl(unittest.TestCase):
    """Test the Heat Control thermostat."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.temperature_unit = TEMP_CELCIUS
        thermostat.setup(self.hass, {'thermostat': {
            'platform': 'heat_control',
            'name': 'test',
            'heater': ent_switch,
            'target_sensor': ent_sensor
        }})

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_defaults_to_unknown(self):
        """Test the setting of defaults to unknown."""
        self.assertEqual('unknown', self.hass.states.get(entity).state)

    def test_default_setup_params(self):
        """Test the setup with default parameters."""
        state = self.hass.states.get(entity)
        self.assertEqual(7, state.attributes.get('min_temp'))
        self.assertEqual(35, state.attributes.get('max_temp'))
        self.assertEqual(None, state.attributes.get('temperature'))

    def test_custom_setup_params(self):
        """Test the setup with custom parameters."""
        thermostat.setup(self.hass, {'thermostat': {
            'platform': 'heat_control',
            'name': 'test',
            'heater': ent_switch,
            'target_sensor': ent_sensor,
            'min_temp': min_temp,
            'max_temp': max_temp,
            'target_temp': target_temp
        }})
        state = self.hass.states.get(entity)
        self.assertEqual(min_temp, state.attributes.get('min_temp'))
        self.assertEqual(max_temp, state.attributes.get('max_temp'))
        self.assertEqual(target_temp, state.attributes.get('temperature'))
        self.assertEqual(str(target_temp), self.hass.states.get(entity).state)

    def test_set_target_temp(self):
        """Test the setting of the target temperature."""
        thermostat.set_temperature(self.hass, 30)
        self.hass.pool.block_till_done()
        self.assertEqual('30.0', self.hass.states.get(entity).state)

    def test_set_target_temp_turns_on_heater(self):
        """Test if target temperature turn heater on."""
        self._setup_switch(False)
        self._setup_sensor(25)
        self.hass.pool.block_till_done()
        thermostat.set_temperature(self.hass, 30)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_ON, call.service)
        self.assertEqual(ent_switch, call.data['entity_id'])

    def test_set_target_temp_turns_off_heater(self):
        """Test if target temperature turn heater off."""
        self._setup_switch(True)
        self._setup_sensor(30)
        self.hass.pool.block_till_done()
        thermostat.set_temperature(self.hass, 25)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual(ent_switch, call.data['entity_id'])

    def test_set_temp_change_turns_on_heater(self):
        """Test if temperature change turn heater on."""
        self._setup_switch(False)
        thermostat.set_temperature(self.hass, 30)
        self.hass.pool.block_till_done()
        self._setup_sensor(25)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_ON, call.service)
        self.assertEqual(ent_switch, call.data['entity_id'])

    def test_temp_change_turns_off_heater(self):
        """Test if temperature change turn heater off."""
        self._setup_switch(True)
        thermostat.set_temperature(self.hass, 25)
        self.hass.pool.block_till_done()
        self._setup_sensor(30)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(self.calls))
        call = self.calls[0]
        self.assertEqual('switch', call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual(ent_switch, call.data['entity_id'])

    def _setup_sensor(self, temp, unit=TEMP_CELCIUS):
        """Setup the test sensor."""
        self.hass.states.set(ent_sensor, temp, {
            ATTR_UNIT_OF_MEASUREMENT: unit
        })

    def _setup_switch(self, is_on):
        """Setup the test switch."""
        self.hass.states.set(ent_switch, STATE_ON if is_on else STATE_OFF)
        self.calls = []

        def log_call(call):
            """Log service calls."""
            self.calls.append(call)

        self.hass.services.register('switch', SERVICE_TURN_ON, log_call)
        self.hass.services.register('switch', SERVICE_TURN_OFF, log_call)
