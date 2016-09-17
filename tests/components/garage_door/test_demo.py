"""The tests for the Demo Garage door platform."""
import unittest

from homeassistant.bootstrap import setup_component
import homeassistant.components.garage_door as gd

from tests.common import get_test_home_assistant


LEFT = 'garage_door.left_garage_door'
RIGHT = 'garage_door.right_garage_door'


class TestGarageDoorDemo(unittest.TestCase):
    """Test the demo garage door."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.assertTrue(setup_component(self.hass, gd.DOMAIN, {
            'garage_door': {
                'platform': 'demo'
            }
        }))

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_is_closed(self):
        """Test if door is closed."""
        self.assertTrue(gd.is_closed(self.hass, LEFT))
        self.hass.states.is_state(LEFT, 'close')

        self.assertFalse(gd.is_closed(self.hass, RIGHT))
        self.hass.states.is_state(RIGHT, 'open')

    def test_open_door(self):
        """Test opeing of the door."""
        gd.open_door(self.hass, LEFT)
        self.hass.block_till_done()

        self.assertFalse(gd.is_closed(self.hass, LEFT))

    def test_close_door(self):
        """Test closing ot the door."""
        gd.close_door(self.hass, RIGHT)
        self.hass.block_till_done()

        self.assertTrue(gd.is_closed(self.hass, RIGHT))
