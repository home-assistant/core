"""The tests for the demo climate component."""
import unittest

from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
)
from homeassistant.bootstrap import setup_component
from homeassistant.components import climate

from tests.common import get_test_home_assistant


ENTITY_CLIMATE = 'climate.hvac'
ENTITY_ECOBEE = 'climate.ecobee'


class TestDemoClimate(unittest.TestCase):
    """Test the demo climate hvac."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        self.assertTrue(setup_component(self.hass, climate.DOMAIN, {
            'climate': {
                'platform': 'demo',
            }}))

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_params(self):
        """Test the inititial parameters."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(21, state.attributes.get('temperature'))
        self.assertEqual('on', state.attributes.get('away_mode'))
        self.assertEqual(22, state.attributes.get('current_temperature'))
        self.assertEqual("On High", state.attributes.get('fan_mode'))
        self.assertEqual(67, state.attributes.get('humidity'))
        self.assertEqual(54, state.attributes.get('current_humidity'))
        self.assertEqual("Off", state.attributes.get('swing_mode'))
        self.assertEqual("cool", state.attributes.get('operation_mode'))
        self.assertEqual('off', state.attributes.get('aux_heat'))

    def test_default_setup_params(self):
        """Test the setup with default parameters."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(7, state.attributes.get('min_temp'))
        self.assertEqual(35, state.attributes.get('max_temp'))
        self.assertEqual(30, state.attributes.get('min_humidity'))
        self.assertEqual(99, state.attributes.get('max_humidity'))

    def test_set_only_target_temp_bad_attr(self):
        """Test setting the target temperature without required attribute."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(21, state.attributes.get('temperature'))
        climate.set_temperature(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        self.assertEqual(21, state.attributes.get('temperature'))

    def test_set_only_target_temp(self):
        """Test the setting of the target temperature."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(21, state.attributes.get('temperature'))
        climate.set_temperature(self.hass, 30, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(30.0, state.attributes.get('temperature'))

    def test_set_target_temp_range(self):
        """Test the setting of the target temperature with range."""
        state = self.hass.states.get(ENTITY_ECOBEE)
        self.assertEqual(23.0, state.attributes.get('temperature'))
        self.assertEqual(21.0, state.attributes.get('target_temp_low'))
        self.assertEqual(24.0, state.attributes.get('target_temp_high'))
        climate.set_temperature(self.hass, 30, ENTITY_ECOBEE, 25, 20)
        self.hass.pool.block_till_done()
        state = self.hass.states.get(ENTITY_ECOBEE)
        self.assertEqual(30.0, state.attributes.get('temperature'))
        self.assertEqual(20.0, state.attributes.get('target_temp_low'))
        self.assertEqual(25.0, state.attributes.get('target_temp_high'))

    def test_set_target_temp_range_bad_attr(self):
        """Test setting the target temperature range without required
           attribute."""
        state = self.hass.states.get(ENTITY_ECOBEE)
        self.assertEqual(23, state.attributes.get('temperature'))
        self.assertEqual(21.0, state.attributes.get('target_temp_low'))
        self.assertEqual(24.0, state.attributes.get('target_temp_high'))
        climate.set_temperature(self.hass, None, ENTITY_ECOBEE, None, None)
        self.hass.pool.block_till_done()
        state = self.hass.states.get(ENTITY_ECOBEE)
        self.assertEqual(23, state.attributes.get('temperature'))
        self.assertEqual(21.0, state.attributes.get('target_temp_low'))
        self.assertEqual(24.0, state.attributes.get('target_temp_high'))

    def test_set_target_humidity_bad_attr(self):
        """Test setting the target humidity without required attribute."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(67, state.attributes.get('humidity'))
        climate.set_humidity(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(67, state.attributes.get('humidity'))

    def test_set_target_humidity(self):
        """Test the setting of the target humidity."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(67, state.attributes.get('humidity'))
        climate.set_humidity(self.hass, 64, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(64.0, state.attributes.get('humidity'))

    def test_set_fan_mode_bad_attr(self):
        """Test setting fan mode without required attribute."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("On High", state.attributes.get('fan_mode'))
        climate.set_fan_mode(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("On High", state.attributes.get('fan_mode'))

    def test_set_fan_mode(self):
        """Test setting of new fan mode."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("On High", state.attributes.get('fan_mode'))
        climate.set_fan_mode(self.hass, "On Low", ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("On Low", state.attributes.get('fan_mode'))

    def test_set_swing_mode_bad_attr(self):
        """Test setting swing mode without required attribute."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("Off", state.attributes.get('swing_mode'))
        climate.set_swing_mode(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("Off", state.attributes.get('swing_mode'))

    def test_set_swing(self):
        """Test setting of new swing mode."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("Off", state.attributes.get('swing_mode'))
        climate.set_swing_mode(self.hass, "Auto", ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("Auto", state.attributes.get('swing_mode'))

    def test_set_operation_bad_attr_and_state(self):
        """Test setting operation mode without required attribute, and
           check the state."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("cool", state.attributes.get('operation_mode'))
        self.assertEqual("cool", state.state)
        climate.set_operation_mode(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("cool", state.attributes.get('operation_mode'))
        self.assertEqual("cool", state.state)

    def test_set_operation(self):
        """Test setting of new operation mode."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("cool", state.attributes.get('operation_mode'))
        self.assertEqual("cool", state.state)
        climate.set_operation_mode(self.hass, "heat", ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("heat", state.attributes.get('operation_mode'))
        self.assertEqual("heat", state.state)

    def test_set_away_mode_bad_attr(self):
        """Test setting the away mode without required attribute."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('on', state.attributes.get('away_mode'))
        climate.set_away_mode(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        self.assertEqual('on', state.attributes.get('away_mode'))

    def test_set_away_mode_on(self):
        """Test setting the away mode on/true."""
        climate.set_away_mode(self.hass, True, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('on', state.attributes.get('away_mode'))

    def test_set_away_mode_off(self):
        """Test setting the away mode off/false."""
        climate.set_away_mode(self.hass, False, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('away_mode'))

    def test_set_aux_heat_bad_attr(self):
        """Test setting the auxillary heater without required attribute."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('aux_heat'))
        climate.set_aux_heat(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        self.assertEqual('off', state.attributes.get('aux_heat'))

    def test_set_aux_heat_on(self):
        """Test setting the axillary heater on/true."""
        climate.set_aux_heat(self.hass, True, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('on', state.attributes.get('aux_heat'))

    def test_set_aux_heat_off(self):
        """Test setting the auxillary heater off/false."""
        climate.set_aux_heat(self.hass, False, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('aux_heat'))
