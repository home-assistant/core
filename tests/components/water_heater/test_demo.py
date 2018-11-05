"""The tests for the demo water_heater component."""
import unittest

from homeassistant.util.unit_system import (
    IMPERIAL_SYSTEM
)
from homeassistant.setup import setup_component
from homeassistant.components import water_heater

from tests.common import get_test_home_assistant
from tests.components.water_heater import common


ENTITY_WATER_HEATER = 'water_heater.demo_water_heater'
ENTITY_WATER_HEATER_CELSIUS = 'water_heater.demo_water_heater_celsius'


class TestDemowater_heater(unittest.TestCase):
    """Test the demo water_heater."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = IMPERIAL_SYSTEM
        self.assertTrue(setup_component(self.hass, water_heater.DOMAIN, {
            'water_heater': {
                'platform': 'demo',
            }}))

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_params(self):
        """Test the initial parameters."""
        state = self.hass.states.get(ENTITY_WATER_HEATER)
        self.assertEqual(119, state.attributes.get('temperature'))
        self.assertEqual('off', state.attributes.get('away_mode'))
        self.assertEqual("eco", state.attributes.get('operation_mode'))

    def test_default_setup_params(self):
        """Test the setup with default parameters."""
        state = self.hass.states.get(ENTITY_WATER_HEATER)
        self.assertEqual(110, state.attributes.get('min_temp'))
        self.assertEqual(140, state.attributes.get('max_temp'))

    def test_set_only_target_temp_bad_attr(self):
        """Test setting the target temperature without required attribute."""
        state = self.hass.states.get(ENTITY_WATER_HEATER)
        self.assertEqual(119, state.attributes.get('temperature'))
        common.set_temperature(self.hass, None, ENTITY_WATER_HEATER)
        self.hass.block_till_done()
        self.assertEqual(119, state.attributes.get('temperature'))

    def test_set_only_target_temp(self):
        """Test the setting of the target temperature."""
        state = self.hass.states.get(ENTITY_WATER_HEATER)
        self.assertEqual(119, state.attributes.get('temperature'))
        common.set_temperature(self.hass, 110, ENTITY_WATER_HEATER)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_WATER_HEATER)
        self.assertEqual(110, state.attributes.get('temperature'))

    def test_set_operation_bad_attr_and_state(self):
        """Test setting operation mode without required attribute.

        Also check the state.
        """
        state = self.hass.states.get(ENTITY_WATER_HEATER)
        self.assertEqual("eco", state.attributes.get('operation_mode'))
        self.assertEqual("eco", state.state)
        common.set_operation_mode(self.hass, None, ENTITY_WATER_HEATER)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_WATER_HEATER)
        self.assertEqual("eco", state.attributes.get('operation_mode'))
        self.assertEqual("eco", state.state)

    def test_set_operation(self):
        """Test setting of new operation mode."""
        state = self.hass.states.get(ENTITY_WATER_HEATER)
        self.assertEqual("eco", state.attributes.get('operation_mode'))
        self.assertEqual("eco", state.state)
        common.set_operation_mode(self.hass, "electric", ENTITY_WATER_HEATER)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_WATER_HEATER)
        self.assertEqual("electric", state.attributes.get('operation_mode'))
        self.assertEqual("electric", state.state)

    def test_set_away_mode_bad_attr(self):
        """Test setting the away mode without required attribute."""
        state = self.hass.states.get(ENTITY_WATER_HEATER)
        self.assertEqual('off', state.attributes.get('away_mode'))
        common.set_away_mode(self.hass, None, ENTITY_WATER_HEATER)
        self.hass.block_till_done()
        self.assertEqual('off', state.attributes.get('away_mode'))

    def test_set_away_mode_on(self):
        """Test setting the away mode on/true."""
        common.set_away_mode(self.hass, True, ENTITY_WATER_HEATER)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_WATER_HEATER)
        self.assertEqual('on', state.attributes.get('away_mode'))

    def test_set_away_mode_off(self):
        """Test setting the away mode off/false."""
        common.set_away_mode(self.hass, False, ENTITY_WATER_HEATER_CELSIUS)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_WATER_HEATER_CELSIUS)
        self.assertEqual('off', state.attributes.get('away_mode'))

    def test_set_only_target_temp_with_convert(self):
        """Test the setting of the target temperature."""
        state = self.hass.states.get(ENTITY_WATER_HEATER_CELSIUS)
        self.assertEqual(113, state.attributes.get('temperature'))
        common.set_temperature(self.hass, 114, ENTITY_WATER_HEATER_CELSIUS)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_WATER_HEATER_CELSIUS)
        self.assertEqual(114, state.attributes.get('temperature'))
