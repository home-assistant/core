"""The tests for the demo thermostat."""
import unittest

from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
)
from homeassistant.components import thermostat

from tests.common import get_test_home_assistant


ENTITY_NEST = 'thermostat.nest'


class TestDemoThermostat(unittest.TestCase):
    """Test the Heat Control thermostat."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        self.assertTrue(thermostat.setup(self.hass, {'thermostat': {
            'platform': 'demo',
        }}))

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_params(self):
        """Test the inititial parameters."""
        state = self.hass.states.get(ENTITY_NEST)
        self.assertEqual(21, state.attributes.get('temperature'))
        self.assertEqual('off', state.attributes.get('away_mode'))
        self.assertEqual(19, state.attributes.get('current_temperature'))
        self.assertEqual('off', state.attributes.get('fan'))

    def test_default_setup_params(self):
        """Test the setup with default parameters."""
        state = self.hass.states.get(ENTITY_NEST)
        self.assertEqual(7, state.attributes.get('min_temp'))
        self.assertEqual(35, state.attributes.get('max_temp'))

    def test_set_target_temp_bad_attr(self):
        """Test setting the target temperature without required attribute."""
        self.assertEqual('21.0', self.hass.states.get(ENTITY_NEST).state)
        thermostat.set_temperature(self.hass, None, ENTITY_NEST)
        self.hass.block_till_done()
        self.assertEqual('21.0', self.hass.states.get(ENTITY_NEST).state)

    def test_set_target_temp(self):
        """Test the setting of the target temperature."""
        thermostat.set_temperature(self.hass, 30, ENTITY_NEST)
        self.hass.block_till_done()
        self.assertEqual('30.0', self.hass.states.get(ENTITY_NEST).state)

    def test_set_away_mode_bad_attr(self):
        """Test setting the away mode without required attribute."""
        state = self.hass.states.get(ENTITY_NEST)
        self.assertEqual('off', state.attributes.get('away_mode'))
        thermostat.set_away_mode(self.hass, None, ENTITY_NEST)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_NEST)
        self.assertEqual('off', state.attributes.get('away_mode'))

    def test_set_away_mode_on(self):
        """Test setting the away mode on/true."""
        thermostat.set_away_mode(self.hass, True, ENTITY_NEST)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_NEST)
        self.assertEqual('on', state.attributes.get('away_mode'))

    def test_set_away_mode_off(self):
        """Test setting the away mode off/false."""
        thermostat.set_away_mode(self.hass, False, ENTITY_NEST)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_NEST)
        self.assertEqual('off', state.attributes.get('away_mode'))

    def test_set_fan_mode_on_bad_attr(self):
        """Test setting the fan mode on/true without required attribute."""
        state = self.hass.states.get(ENTITY_NEST)
        self.assertEqual('off', state.attributes.get('fan'))
        thermostat.set_fan_mode(self.hass, None, ENTITY_NEST)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_NEST)
        self.assertEqual('off', state.attributes.get('fan'))

    def test_set_fan_mode_on(self):
        """Test setting the fan mode on/true."""
        thermostat.set_fan_mode(self.hass, True, ENTITY_NEST)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_NEST)
        self.assertEqual('on', state.attributes.get('fan'))

    def test_set_fan_mode_off(self):
        """Test setting the fan mode off/false."""
        thermostat.set_fan_mode(self.hass, False, ENTITY_NEST)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_NEST)
        self.assertEqual('off', state.attributes.get('fan'))
