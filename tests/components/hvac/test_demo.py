"""The tests for the demo hvac."""
import unittest

from homeassistant.bootstrap import setup_component
from homeassistant.components import hvac
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
)

from tests.common import get_test_home_assistant


ENTITY_HVAC = 'hvac.hvac'


class TestDemoHvac(unittest.TestCase):
    """Test the demo hvac."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        self.assertTrue(setup_component(self.hass, hvac.DOMAIN, {'hvac': {
            'platform': 'demo',
        }}))

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_params(self):
        """Test the inititial parameters."""
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual(21, state.attributes.get('temperature'))
        self.assertEqual('on', state.attributes.get('away_mode'))
        self.assertEqual(22, state.attributes.get('current_temperature'))
        self.assertEqual("On High", state.attributes.get('fan_mode'))
        self.assertEqual(67, state.attributes.get('humidity'))
        self.assertEqual(54, state.attributes.get('current_humidity'))
        self.assertEqual("Off", state.attributes.get('swing_mode'))
        self.assertEqual("Cool", state.attributes.get('operation_mode'))
        self.assertEqual('off', state.attributes.get('aux_heat'))

    def test_default_setup_params(self):
        """Test the setup with default parameters."""
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual(19, state.attributes.get('min_temp'))
        self.assertEqual(30, state.attributes.get('max_temp'))
        self.assertEqual(30, state.attributes.get('min_humidity'))
        self.assertEqual(99, state.attributes.get('max_humidity'))

    def test_set_target_temp_bad_attr(self):
        """Test setting the target temperature without required attribute."""
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual(21, state.attributes.get('temperature'))
        hvac.set_temperature(self.hass, None, ENTITY_HVAC)
        self.hass.block_till_done()
        self.assertEqual(21, state.attributes.get('temperature'))

    def test_set_target_temp(self):
        """Test the setting of the target temperature."""
        hvac.set_temperature(self.hass, 30, ENTITY_HVAC)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual(30.0, state.attributes.get('temperature'))

    def test_set_target_humidity_bad_attr(self):
        """Test setting the target humidity without required attribute."""
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual(67, state.attributes.get('humidity'))
        hvac.set_humidity(self.hass, None, ENTITY_HVAC)
        self.hass.block_till_done()
        self.assertEqual(67, state.attributes.get('humidity'))

    def test_set_target_humidity(self):
        """Test the setting of the target humidity."""
        hvac.set_humidity(self.hass, 64, ENTITY_HVAC)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual(64.0, state.attributes.get('humidity'))

    def test_set_fan_mode_bad_attr(self):
        """Test setting fan mode without required attribute."""
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual("On High", state.attributes.get('fan_mode'))
        hvac.set_fan_mode(self.hass, None, ENTITY_HVAC)
        self.hass.block_till_done()
        self.assertEqual("On High", state.attributes.get('fan_mode'))

    def test_set_fan_mode(self):
        """Test setting of new fan mode."""
        hvac.set_fan_mode(self.hass, "On Low", ENTITY_HVAC)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual("On Low", state.attributes.get('fan_mode'))

    def test_set_swing_mode_bad_attr(self):
        """Test setting swing mode without required attribute."""
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual("Off", state.attributes.get('swing_mode'))
        hvac.set_swing_mode(self.hass, None, ENTITY_HVAC)
        self.hass.block_till_done()
        self.assertEqual("Off", state.attributes.get('swing_mode'))

    def test_set_swing(self):
        """Test setting of new swing mode."""
        hvac.set_swing_mode(self.hass, "Auto", ENTITY_HVAC)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual("Auto", state.attributes.get('swing_mode'))

    def test_set_operation_bad_attr(self):
        """Test setting operation mode without required attribute."""
        self.assertEqual("Cool", self.hass.states.get(ENTITY_HVAC).state)
        hvac.set_operation_mode(self.hass, None, ENTITY_HVAC)
        self.hass.block_till_done()
        self.assertEqual("Cool", self.hass.states.get(ENTITY_HVAC).state)

    def test_set_operation(self):
        """Test setting of new operation mode."""
        hvac.set_operation_mode(self.hass, "Heat", ENTITY_HVAC)
        self.hass.block_till_done()
        self.assertEqual("Heat", self.hass.states.get(ENTITY_HVAC).state)

    def test_set_away_mode_bad_attr(self):
        """Test setting the away mode without required attribute."""
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual('on', state.attributes.get('away_mode'))
        hvac.set_away_mode(self.hass, None, ENTITY_HVAC)
        self.hass.block_till_done()
        self.assertEqual('on', state.attributes.get('away_mode'))

    def test_set_away_mode_on(self):
        """Test setting the away mode on/true."""
        hvac.set_away_mode(self.hass, True, ENTITY_HVAC)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual('on', state.attributes.get('away_mode'))

    def test_set_away_mode_off(self):
        """Test setting the away mode off/false."""
        hvac.set_away_mode(self.hass, False, ENTITY_HVAC)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual('off', state.attributes.get('away_mode'))

    def test_set_aux_heat_bad_attr(self):
        """Test setting the auxillary heater without required attribute."""
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual('off', state.attributes.get('aux_heat'))
        hvac.set_aux_heat(self.hass, None, ENTITY_HVAC)
        self.hass.block_till_done()
        self.assertEqual('off', state.attributes.get('aux_heat'))

    def test_set_aux_heat_on(self):
        """Test setting the axillary heater on/true."""
        hvac.set_aux_heat(self.hass, True, ENTITY_HVAC)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual('on', state.attributes.get('aux_heat'))

    def test_set_aux_heat_off(self):
        """Test setting the auxillary heater off/false."""
        hvac.set_aux_heat(self.hass, False, ENTITY_HVAC)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_HVAC)
        self.assertEqual('off', state.attributes.get('aux_heat'))
