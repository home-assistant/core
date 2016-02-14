"""
tests.components.garage_door.test_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests demo garage door component.
"""
import unittest

import homeassistant.components.garage_door as gd

from tests.common import get_test_home_assistant


LEFT = 'garage_door.left_garage_door'
RIGHT = 'garage_door.right_garage_door'


class TestGarageDoorDemo(unittest.TestCase):
    """ Test the demo garage door. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = get_test_home_assistant()
        self.assertTrue(gd.setup(self.hass, {
            'garage_door': {
                'platform': 'demo'
            }
        }))

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_is_closed(self):
        self.assertTrue(gd.is_closed(self.hass, LEFT))
        self.hass.states.is_state(LEFT, 'close')

        self.assertFalse(gd.is_closed(self.hass, RIGHT))
        self.hass.states.is_state(RIGHT, 'open')

    def test_open_door(self):
        gd.open_door(self.hass, LEFT)

        self.hass.pool.block_till_done()

        self.assertFalse(gd.is_closed(self.hass, LEFT))

    def test_close_door(self):
        gd.close_door(self.hass, RIGHT)

        self.hass.pool.block_till_done()

        self.assertTrue(gd.is_closed(self.hass, RIGHT))
