"""
tests.test_component_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests demo component.
"""
import unittest

import homeassistant as ha
import homeassistant.components.demo as demo


class TestDemo(unittest.TestCase):
    """ Test the demo module. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_if_demo_state_shows_by_default(self):
        """ Test if demo state shows if we give no configuration. """
        demo.setup(self.hass, {demo.DOMAIN: {}})

        self.assertIsNotNone(self.hass.states.get('a.Demo_Mode'))

    def test_hiding_demo_state(self):
        """ Test if you can hide the demo card. """
        demo.setup(self.hass, {demo.DOMAIN: {'hide_demo_state': 1}})

        self.assertIsNone(self.hass.states.get('a.Demo_Mode'))
