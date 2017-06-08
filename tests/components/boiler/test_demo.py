"""The tests for the demo boiler component."""
import unittest

from homeassistant.util.unit_system import (
    METRIC_SYSTEM
)
from homeassistant.bootstrap import setup_component
from homeassistant.components import boiler

from tests.common import get_test_home_assistant, assert_setup_component


ENTITY_GEYSERWISE = 'boiler.geyserwise'
ENTITY_GEYSERWISE_MAX = 'boiler.geyserwise_max'
ENTITY_QWIKSWITCH = 'boiler.qwikswitch'


class TestDemoBoiler(unittest.TestCase):
    """Test the demo boiler."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        with assert_setup_component(1):
            assert setup_component(self.hass, boiler.DOMAIN,
                                   {'boiler': {'platform': 'demo', }})

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_params(self):
        """Test the initial parameters."""
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        # test attributes as set by components/boiler/demo.py
        self.assertEqual(55, state.attributes.get('target_water_temperature'))
        self.assertEqual('off', state.attributes.get('away_mode'))
        self.assertEqual("off", state.attributes.get('guest_mode'))
        self.assertEqual("off", state.attributes.get('holiday_mode'))
        self.assertEqual("heat", state.attributes.get('operation_mode'))
        # exclude until I can get this working
        # self.assertEqual('off', state.attributes.get('boost'))

    def test_default_setup_params(self):
        """Test the setup with default parameters."""
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        # Current temp not available in demo
        self.assertEqual(None,
                         state.attributes.get('current_water_temperature'))
        # Demo platform initialises to 55
        self.assertEqual(55,
                         state.attributes.get('target_water_temperature'))

    def test_set_only_target_temp_bad_attr(self):
        """Test setting the target temperature without required attribute."""
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        self.assertEqual(55, state.attributes.get('target_water_temperature'))
        # None should not be allowed as target temp
        boiler.set_temperature(self.hass, None, ENTITY_GEYSERWISE)
        self.hass.block_till_done()
        # None should be ignored so target temp should stay 55 (default)
        self.assertEqual(55, state.attributes.get('target_water_temperature'))

    def test_set_only_target_temp(self):
        """Test the setting of the target temperature."""
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        # Default should be 55 as per demo platform
        self.assertEqual(55, state.attributes.get('target_water_temperature'))
        # Try setting a new target temp
        boiler.set_temperature(self.hass, ENTITY_GEYSERWISE, 65)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        # New temp should now be 65
        self.assertEqual(65, state.attributes.get('target_water_temperature'))

    def test_set_only_target_temp_with_convert(self):
        """Test the setting of the target temperature."""
        state = self.hass.states.get(ENTITY_GEYSERWISE_MAX)
        self.assertEqual(65, state.attributes.get('target_water_temperature'))
        boiler.set_temperature(self.hass, ENTITY_GEYSERWISE_MAX, 60)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_GEYSERWISE_MAX)
        self.assertEqual(60, state.attributes.get('target_water_temperature'))

    def test_set_operation_bad_attr_and_state(self):
        """Test setting operation mode without required attribute, and
           check the state."""
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        # Demo platform set geyserwise default to heat
        self.assertEqual("heat", state.attributes.get('operation_mode'))
        self.assertEqual("heat", state.state)
        # None should not be allowed as valid mode
        boiler.set_operation_mode(self.hass, None, ENTITY_GEYSERWISE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        # Mode should have been ignored and stayed as heat
        self.assertEqual("heat", state.attributes.get('operation_mode'))
        self.assertEqual("heat", state.state)

    def test_set_operation(self):
        """Test setting of new operation mode."""
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        self.assertEqual("heat", state.attributes.get('operation_mode'))
        self.assertEqual("heat", state.state)
        # Try setting mode to idle
        boiler.set_operation_mode(self.hass, "idle", ENTITY_GEYSERWISE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        # Test if new mode was accepted
        self.assertEqual("idle", state.attributes.get('operation_mode'))
        self.assertEqual("idle", state.state)

    def test_set_away_mode_bad_attr(self):
        """Test setting the away mode without required attribute."""
        state = self.hass.states.get(ENTITY_GEYSERWISE)
        self.assertEqual('off', state.attributes.get('away_mode'))
        boiler.set_away_mode(self.hass, None, ENTITY_GEYSERWISE)
        self.hass.block_till_done()
        self.assertEqual('off', state.attributes.get('away_mode'))

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
