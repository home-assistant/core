"""The tests for the demo light component."""
# pylint: disable=protected-access
import unittest

from homeassistant.setup import setup_component
import homeassistant.components.light as light

from tests.common import get_test_home_assistant

ENTITY_LIGHT = 'light.bed_light'


class TestDemoLight(unittest.TestCase):
    """Test the demo light."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.assertTrue(setup_component(self.hass, light.DOMAIN, {'light': {
            'platform': 'demo',
        }}))

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_state_attributes(self):
        """Test light state attributes."""
        light.turn_on(
            self.hass, ENTITY_LIGHT, xy_color=(.4, .4), brightness=25)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_LIGHT)
        self.assertTrue(light.is_on(self.hass, ENTITY_LIGHT))
        self.assertEqual((0.4, 0.4), state.attributes.get(
            light.ATTR_XY_COLOR))
        self.assertEqual(25, state.attributes.get(light.ATTR_BRIGHTNESS))
        self.assertEqual(
            (255, 234, 164), state.attributes.get(light.ATTR_RGB_COLOR))
        self.assertEqual('rainbow', state.attributes.get(light.ATTR_EFFECT))
        light.turn_on(
            self.hass, ENTITY_LIGHT, rgb_color=(251, 253, 255),
            white_value=254)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_LIGHT)
        self.assertEqual(254, state.attributes.get(light.ATTR_WHITE_VALUE))
        self.assertEqual(
            (250, 252, 255), state.attributes.get(light.ATTR_RGB_COLOR))
        self.assertEqual(
            (0.319, 0.326), state.attributes.get(light.ATTR_XY_COLOR))
        light.turn_on(self.hass, ENTITY_LIGHT, color_temp=400, effect='none')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_LIGHT)
        self.assertEqual(400, state.attributes.get(light.ATTR_COLOR_TEMP))
        self.assertEqual(153, state.attributes.get(light.ATTR_MIN_MIREDS))
        self.assertEqual(500, state.attributes.get(light.ATTR_MAX_MIREDS))
        self.assertEqual('none', state.attributes.get(light.ATTR_EFFECT))
        light.turn_on(self.hass, ENTITY_LIGHT, kelvin=3000, brightness_pct=50)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_LIGHT)
        self.assertEqual(333, state.attributes.get(light.ATTR_COLOR_TEMP))
        self.assertEqual(127, state.attributes.get(light.ATTR_BRIGHTNESS))

    def test_turn_off(self):
        """Test light turn off method."""
        light.turn_on(self.hass, ENTITY_LIGHT)
        self.hass.block_till_done()
        self.assertTrue(light.is_on(self.hass, ENTITY_LIGHT))
        light.turn_off(self.hass, ENTITY_LIGHT)
        self.hass.block_till_done()
        self.assertFalse(light.is_on(self.hass, ENTITY_LIGHT))

    def test_turn_off_without_entity_id(self):
        """Test light turn off all lights."""
        light.turn_on(self.hass, ENTITY_LIGHT)
        self.hass.block_till_done()
        self.assertTrue(light.is_on(self.hass, ENTITY_LIGHT))
        light.turn_off(self.hass)
        self.hass.block_till_done()
        self.assertFalse(light.is_on(self.hass, ENTITY_LIGHT))
