"""The tests for the Switch component."""
# pylint: disable=protected-access
import unittest

from homeassistant.setup import setup_component
from homeassistant import loader
from homeassistant.components import switch
from homeassistant.const import STATE_ON, STATE_OFF, CONF_PLATFORM

from tests.common import get_test_home_assistant


class TestSwitch(unittest.TestCase):
    """Test the switch module."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        platform = loader.get_component(self.hass, 'switch.test')
        platform.init()
        # Switch 1 is ON, switch 2 is OFF
        self.switch_1, self.switch_2, self.switch_3 = \
            platform.DEVICES

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_methods(self):
        """Test is_on, turn_on, turn_off methods."""
        self.assertTrue(setup_component(
            self.hass, switch.DOMAIN, {switch.DOMAIN: {CONF_PLATFORM: 'test'}}
        ))
        self.assertTrue(switch.is_on(self.hass))
        self.assertEqual(
            STATE_ON,
            self.hass.states.get(switch.ENTITY_ID_ALL_SWITCHES).state)
        self.assertTrue(switch.is_on(self.hass, self.switch_1.entity_id))
        self.assertFalse(switch.is_on(self.hass, self.switch_2.entity_id))
        self.assertFalse(switch.is_on(self.hass, self.switch_3.entity_id))

        switch.turn_off(self.hass, self.switch_1.entity_id)
        switch.turn_on(self.hass, self.switch_2.entity_id)

        self.hass.block_till_done()

        self.assertTrue(switch.is_on(self.hass))
        self.assertFalse(switch.is_on(self.hass, self.switch_1.entity_id))
        self.assertTrue(switch.is_on(self.hass, self.switch_2.entity_id))

        # Turn all off
        switch.turn_off(self.hass)

        self.hass.block_till_done()

        self.assertFalse(switch.is_on(self.hass))
        self.assertEqual(
            STATE_OFF,
            self.hass.states.get(switch.ENTITY_ID_ALL_SWITCHES).state)
        self.assertFalse(switch.is_on(self.hass, self.switch_1.entity_id))
        self.assertFalse(switch.is_on(self.hass, self.switch_2.entity_id))
        self.assertFalse(switch.is_on(self.hass, self.switch_3.entity_id))

        # Turn all on
        switch.turn_on(self.hass)

        self.hass.block_till_done()

        self.assertTrue(switch.is_on(self.hass))
        self.assertEqual(
            STATE_ON,
            self.hass.states.get(switch.ENTITY_ID_ALL_SWITCHES).state)
        self.assertTrue(switch.is_on(self.hass, self.switch_1.entity_id))
        self.assertTrue(switch.is_on(self.hass, self.switch_2.entity_id))
        self.assertTrue(switch.is_on(self.hass, self.switch_3.entity_id))

    def test_setup_two_platforms(self):
        """Test with bad configuration."""
        # Test if switch component returns 0 switches
        test_platform = loader.get_component(self.hass, 'switch.test')
        test_platform.init(True)

        loader.set_component(self.hass, 'switch.test2', test_platform)
        test_platform.init(False)

        self.assertTrue(setup_component(
            self.hass, switch.DOMAIN, {
                switch.DOMAIN: {CONF_PLATFORM: 'test'},
                '{} 2'.format(switch.DOMAIN): {CONF_PLATFORM: 'test2'},
            }
        ))
