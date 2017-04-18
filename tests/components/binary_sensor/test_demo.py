"""
tests.components.binary_sensor.test_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests demo binary sensor.
"""
import unittest

import homeassistant.core as ha
from homeassistant.components import binary_sensor
from homeassistant.const import (STATE_OFF, STATE_ON, STATE_UNKNOWN)


class TestBinarySensorDemo(unittest.TestCase):
    """ Test the demo binary sensor. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()
        self.assertTrue(binary_sensor.setup(self.hass, {
            'binary_sensor': {
                'platform': 'demo',
                'name': 'test',
            }
        }))

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_set_on(self):
        self.hass.states.set('binary_sensor.test', STATE_ON)
        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_ON, state.state)

    def test_set_off(self):
        self.hass.states.set('binary_sensor.test', STATE_OFF)
        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_OFF, state.state)

    def test_set_unknown(self):
        self.hass.states.set('binary_sensor.test', STATE_UNKNOWN)
        state = self.hass.states.get('binary_sensor.test')
        self.assertNotEqual(STATE_OFF, STATE_ON, state.state)


