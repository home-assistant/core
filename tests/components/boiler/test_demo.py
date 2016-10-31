"""The tests for the demo boiler component."""
import unittest

from homeassistant.util.unit_system import (
    METRIC_SYSTEM
)
from homeassistant.bootstrap import setup_component
from homeassistant.components import boiler

from tests.common import get_test_home_assistant


ENTITY_GEYSERWISE = 'boiler.geyserwise'
ENTITY_QWIKSWITCH = 'boiler.qwikswitch'
ENTITY_HEATPUMP = 'boiler.heatpump'


class TestDemoBoiler(unittest.TestCase):
    """Test the demo boiler."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        self.assertTrue(setup_component(self.hass, boiler.DOMAIN, {
            'boiler': {
                'platform': 'demo',
            }}))

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()
 
    def test_setup_params(self):
        """Test the initial parameters."""
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        # do I also need to set:
        # name, type, diff_temp, unit_of_measure
        self.assertEqual(55, state.attributes.get('target_water_temp'))
        self.assertEqual('off', state.attributes.get('away_mode'))
        self.assertEqual("off", state.attributes.get('guest_mode'))
        self.assertEqual("off", state.attributes.get('holiday_mode'))
        self.assertEqual("idle", state.attributes.get('operation_mode'))
        self.assertEqual('off', state.attributes.get('boost'))

    def test_default_setup_params(self):
        """Test the setup with default parameters."""
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        self.assertEqual(30, state.attributes.get('current_water_temp'))
        self.assertEqual(65, state.attributes.get('target_water_temp'))

    def test_set_only_target_temp_bad_attr(self):
        """Test setting the target temperature without required attribute."""
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        self.assertEqual(65, state.attributes.get('target_water_temp'))
        boiler.set_temperature(self.hass, None, ENTITY_GEYSERWISE)
        self.hass.block_till_done()
        self.assertEqual(65, state.attributes.get('target_water_temp'))

    def test_set_only_target_temp(self):
        """Test the setting of the target temperature."""
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        self.assertEqual(50, state.attributes.get('target_water_temp'))
        boiler.set_temperature(self.hass, 55, ENTITY_GEYSERWISE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        self.assertEqual(55.0, state.attributes.get('target_water_temp'))

    def test_set_only_target_temp_with_convert(self):
        """Test the setting of the target temperature."""
        state = self.hass.states.get(ENTITY_HEATPUMP)
        self.assertEqual(55, state.attributes.get('target_water_temp'))
        boiler.set_temperature(self.hass, 60, ENTITY_HEATPUMP)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_HEATPUMP)
        self.assertEqual(60.0, state.attributes.get('target_water_temp'))

    def test_set_operation_bad_attr_and_state(self):
        """Test setting operation mode without required attribute, and
           check the state."""
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        self.assertEqual("idle", state.attributes.get('operation_mode'))
        self.assertEqual("idle", state.state)
        boiler.set_operation_mode(self.hass, None, ENTITY_GEYSERWISE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        self.assertEqual("idle", state.attributes.get('operation_mode'))
        self.assertEqual("idle", state.state)

    def test_set_operation(self):
        """Test setting of new operation mode."""
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        self.assertEqual("heat", state.attributes.get('operation_mode'))
        self.assertEqual("heat", state.state)
        boiler.set_operation_mode(self.hass, "pump", ENTITY_GEYSERWISE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        self.assertEqual("idle", state.attributes.get('operation_mode'))
        self.assertEqual("idle", state.state)

    def test_set_away_mode_bad_attr(self):
        """Test setting the away mode without required attribute."""
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        self.assertEqual('on', state.attributes.get('away_mode'))
        boiler.set_away_mode(self.hass, None, ENTITY_GEYSERWISE)
        self.hass.block_till_done()
        self.assertEqual('on', state.attributes.get('away_mode'))

    def test_set_away_mode_on(self):
        """Test setting the away mode on/true."""
        boiler.set_away_mode(self.hass, True, ENTITY_GEYSERWISE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        self.assertEqual('on', state.attributes.get('away_mode'))

    def test_set_away_mode_off(self):
        """Test setting the away mode off/false."""
        boiler.set_away_mode(self.hass, False, ENTITY_GEYSERWISE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        self.assertEqual('off', state.attributes.get('away_mode'))
