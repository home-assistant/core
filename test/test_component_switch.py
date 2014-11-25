"""
test.test_component_chromecast
~~~~~~~~~~~

Tests Chromecast component.
"""
# pylint: disable=too-many-public-methods,protected-access
import unittest

import homeassistant as ha
import homeassistant.loader as loader
import homeassistant.components as components
import homeassistant.components.switch as switch

import mock_switch_platform


class TestSwitch(unittest.TestCase):
    """ Test the switch module. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()
        loader.prepare(self.hass)
        loader.set_component('switch.test', mock_switch_platform)

        self.assertTrue(switch.setup(
            self.hass, {switch.DOMAIN: {ha.CONF_TYPE: 'test'}}
        ))

        # Switch 1 is ON, switch 2 is OFF
        self.switch_1, self.switch_2 = \
            mock_switch_platform.get_switches(None, None)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass._pool.stop()

    def test_methods(self):
        """ Test is_on, turn_on, turn_off methods. """
        self.assertTrue(switch.is_on(self.hass))
        self.assertEqual(
            components.STATE_ON,
            self.hass.states.get(switch.ENTITY_ID_ALL_SWITCHES).state)
        self.assertTrue(switch.is_on(self.hass, self.switch_1.entity_id))
        self.assertFalse(switch.is_on(self.hass, self.switch_2.entity_id))

        switch.turn_off(self.hass, self.switch_1.entity_id)
        switch.turn_on(self.hass, self.switch_2.entity_id)

        self.hass._pool.block_till_done()

        self.assertTrue(switch.is_on(self.hass))
        self.assertFalse(switch.is_on(self.hass, self.switch_1.entity_id))
        self.assertTrue(switch.is_on(self.hass, self.switch_2.entity_id))

        # Turn all off
        switch.turn_off(self.hass)

        self.hass._pool.block_till_done()

        self.assertFalse(switch.is_on(self.hass))
        self.assertEqual(
            components.STATE_OFF,
            self.hass.states.get(switch.ENTITY_ID_ALL_SWITCHES).state)
        self.assertFalse(switch.is_on(self.hass, self.switch_1.entity_id))
        self.assertFalse(switch.is_on(self.hass, self.switch_2.entity_id))

        # Turn all on
        switch.turn_on(self.hass)

        self.hass._pool.block_till_done()

        self.assertTrue(switch.is_on(self.hass))
        self.assertEqual(
            components.STATE_ON,
            self.hass.states.get(switch.ENTITY_ID_ALL_SWITCHES).state)
        self.assertTrue(switch.is_on(self.hass, self.switch_1.entity_id))
        self.assertTrue(switch.is_on(self.hass, self.switch_2.entity_id))

    def test_setup(self):
        # Bogus config
        self.assertFalse(switch.setup(self.hass, {}))

        self.assertFalse(switch.setup(self.hass, {switch.DOMAIN: {}}))

        # Test with non-existing component
        self.assertFalse(switch.setup(
            self.hass, {switch.DOMAIN: {ha.CONF_TYPE: 'nonexisting'}}
        ))

        # Test if switch component returns 0 switches
        mock_switch_platform.fake_no_switches(True)

        self.assertEqual([], mock_switch_platform.get_switches(None, None))

        self.assertFalse(switch.setup(
            self.hass, {switch.DOMAIN: {ha.CONF_TYPE: 'test'}}
        ))

        mock_switch_platform.fake_no_switches(False)
