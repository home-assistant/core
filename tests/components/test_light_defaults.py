"""The tests for the light defaults component."""
# pylint: disable=protected-access
import unittest

from homeassistant.setup import setup_component
import homeassistant.components.light as light

from tests.common import get_test_home_assistant
from homeassistant.components import light_defaults

ENTITY_LIGHT_BED = 'light.bed_light'
ENTITY_LIGHT_CEILING = 'light.ceiling_lights'


class TestLightDefaults(unittest.TestCase):
    """Test the light defaults using the demo lights."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.assertTrue(setup_component(self.hass, light.DOMAIN, {'light': {
            'platform': 'demo',
        }}))
        self.assertTrue(setup_component(self.hass, light_defaults.DOMAIN, {
            'light_defaults': {
                ENTITY_LIGHT_BED: {
                    'color_name': 'blue',
                    'brightness_pct': 25,
                },
                ENTITY_LIGHT_CEILING: {
                    'color_name': 'red',
                    'brightness_pct': 50,
                },
            },
        }))

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_state_attributes_bed(self):
        """Test light state attributes."""
        light.turn_on(
            self.hass, ENTITY_LIGHT_BED, xy_color=(.4, .4), brightness=25)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_LIGHT_BED)
        self.assertTrue(light.is_on(self.hass, ENTITY_LIGHT_BED))
        self.assertEqual((0.4, 0.4), state.attributes.get(
            light.ATTR_XY_COLOR))
        self.assertEqual(25, state.attributes.get(light.ATTR_BRIGHTNESS))
        self.assertEqual(
            (255, 234, 164), state.attributes.get(light.ATTR_RGB_COLOR))

        light.turn_off(self.hass, ENTITY_LIGHT_BED)
        self.hass.block_till_done()
        light.turn_on(self.hass, ENTITY_LIGHT_BED)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_LIGHT_BED)
        self.assertEqual(
            (0, 0, 255), state.attributes.get(light.ATTR_RGB_COLOR))
        self.assertEqual(63, state.attributes.get(light.ATTR_BRIGHTNESS))

    def test_state_attributes_ceiling(self):
        """Test light state attributes."""
        light.turn_on(
            self.hass, ENTITY_LIGHT_CEILING, xy_color=(.4, .4), brightness=25)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_LIGHT_CEILING)
        self.assertTrue(light.is_on(self.hass, ENTITY_LIGHT_CEILING))
        self.assertEqual((0.4, 0.4), state.attributes.get(
            light.ATTR_XY_COLOR))
        self.assertEqual(25, state.attributes.get(light.ATTR_BRIGHTNESS))
        self.assertEqual(
            (255, 234, 164), state.attributes.get(light.ATTR_RGB_COLOR))

        light.turn_off(self.hass, ENTITY_LIGHT_CEILING)
        self.hass.block_till_done()
        light.turn_on(self.hass, ENTITY_LIGHT_CEILING)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_LIGHT_CEILING)
        self.assertEqual(
            (255, 0, 0), state.attributes.get(light.ATTR_RGB_COLOR))
        self.assertEqual(127, state.attributes.get(light.ATTR_BRIGHTNESS))
