"""The tests for the demo light component."""
# pylint: disable=protected-access
import asyncio
import unittest

from homeassistant.core import State, CoreState
from homeassistant.setup import setup_component, async_setup_component
import homeassistant.components.light as light
from homeassistant.helpers.restore_state import DATA_RESTORE_CACHE

from tests.common import get_test_home_assistant, mock_component

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
            self.hass, ENTITY_LIGHT, xy_color=(.4, .6), brightness=25)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_LIGHT)
        self.assertTrue(light.is_on(self.hass, ENTITY_LIGHT))
        self.assertEqual((.4, .6), state.attributes.get(light.ATTR_XY_COLOR))
        self.assertEqual(25, state.attributes.get(light.ATTR_BRIGHTNESS))
        self.assertEqual(
            (76, 95, 0), state.attributes.get(light.ATTR_RGB_COLOR))
        self.assertEqual('rainbow', state.attributes.get(light.ATTR_EFFECT))
        light.turn_on(
            self.hass, ENTITY_LIGHT, rgb_color=(251, 252, 253),
            white_value=254)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_LIGHT)
        self.assertEqual(254, state.attributes.get(light.ATTR_WHITE_VALUE))
        self.assertEqual(
            (251, 252, 253), state.attributes.get(light.ATTR_RGB_COLOR))
        light.turn_on(self.hass, ENTITY_LIGHT, color_temp=400, effect='none')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_LIGHT)
        self.assertEqual(400, state.attributes.get(light.ATTR_COLOR_TEMP))
        self.assertEqual(154, state.attributes.get(light.ATTR_MIN_MIREDS))
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


@asyncio.coroutine
def test_restore_state(hass):
    """Test state gets restored."""
    mock_component(hass, 'recorder')
    hass.state = CoreState.starting
    hass.data[DATA_RESTORE_CACHE] = {
        'light.bed_light': State('light.bed_light', 'on', {
            'brightness': 'value-brightness',
            'color_temp': 'value-color_temp',
            'rgb_color': 'value-rgb_color',
            'xy_color': 'value-xy_color',
            'white_value': 'value-white_value',
            'effect': 'value-effect',
        }),
    }

    yield from async_setup_component(hass, 'light', {
        'light': {
            'platform': 'demo',
        }})

    state = hass.states.get('light.bed_light')
    assert state is not None
    assert state.entity_id == 'light.bed_light'
    assert state.state == 'on'
    assert state.attributes.get('brightness') == 'value-brightness'
    assert state.attributes.get('color_temp') == 'value-color_temp'
    assert state.attributes.get('rgb_color') == 'value-rgb_color'
    assert state.attributes.get('xy_color') == 'value-xy_color'
    assert state.attributes.get('white_value') == 'value-white_value'
    assert state.attributes.get('effect') == 'value-effect'
