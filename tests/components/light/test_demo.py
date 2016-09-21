"""The tests for the demo light component."""
# pylint: disable=too-many-public-methods,protected-access
import unittest

import homeassistant.components.light as light

from tests.common import get_test_home_assistant

ENTITY_LIGHT = 'light.bed_light'


class TestDemoClimate(unittest.TestCase):
    """Test the demo climate hvac."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.assertTrue(light.setup(self.hass, {'light': {
            'platform': 'demo',
        }}))

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_state_attributes(self):
        """Test light state attributes."""
        light.turn_on(
            self.hass, ENTITY_LIGHT, xy_color=(.4, .6), brightness=25)
        self.hass.pool.block_till_done()
        state = self.hass.states.get(ENTITY_LIGHT)
        self.assertTrue(light.is_on(self.hass, ENTITY_LIGHT))
        self.assertEqual((.4, .6), state.attributes.get(light.ATTR_XY_COLOR))
        self.assertEqual(25, state.attributes.get(light.ATTR_BRIGHTNESS))
        self.assertEqual(
            (82, 91, 0), state.attributes.get(light.ATTR_RGB_COLOR))
        light.turn_on(
            self.hass, ENTITY_LIGHT, rgb_color=(251, 252, 253),
            white_value=254)
        self.hass.pool.block_till_done()
        state = self.hass.states.get(ENTITY_LIGHT)
        self.assertEqual(254, state.attributes.get(light.ATTR_WHITE_VALUE))
        self.assertEqual(
            (251, 252, 253), state.attributes.get(light.ATTR_RGB_COLOR))
        light.turn_on(self.hass, ENTITY_LIGHT, color_temp=400)
        self.hass.pool.block_till_done()
        state = self.hass.states.get(ENTITY_LIGHT)
        self.assertEqual(400, state.attributes.get(light.ATTR_COLOR_TEMP))

    def test_turn_off(self):
        """Test light turn off method."""
        light.turn_on(self.hass, ENTITY_LIGHT)
        self.hass.pool.block_till_done()
        self.assertTrue(light.is_on(self.hass, ENTITY_LIGHT))
        light.turn_off(self.hass, ENTITY_LIGHT)
        self.hass.pool.block_till_done()
        self.assertFalse(light.is_on(self.hass, ENTITY_LIGHT))
