"""The tests for the demo light component."""
import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components import light

from tests.components.light import common

ENTITY_LIGHT = 'light.bed_light'


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Set up demo component."""
    hass.loop.run_until_complete(async_setup_component(hass, light.DOMAIN, {
        'light': {
            'platform': 'demo',
        }}))


async def test_state_attributes(hass):
    """Test light state attributes."""
    common.async_turn_on(
        hass, ENTITY_LIGHT, xy_color=(.4, .4), brightness=25)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_LIGHT)
    assert light.is_on(hass, ENTITY_LIGHT)
    assert (0.4, 0.4) == state.attributes.get(light.ATTR_XY_COLOR)
    assert 25 == state.attributes.get(light.ATTR_BRIGHTNESS)
    assert (255, 234, 164) == state.attributes.get(light.ATTR_RGB_COLOR)
    assert 'rainbow' == state.attributes.get(light.ATTR_EFFECT)
    common.async_turn_on(
        hass, ENTITY_LIGHT, rgb_color=(251, 253, 255),
        white_value=254)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_LIGHT)
    assert 254 == state.attributes.get(light.ATTR_WHITE_VALUE)
    assert (250, 252, 255) == state.attributes.get(light.ATTR_RGB_COLOR)
    assert (0.319, 0.326) == state.attributes.get(light.ATTR_XY_COLOR)
    common.async_turn_on(hass, ENTITY_LIGHT, color_temp=400, effect='none')
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_LIGHT)
    assert 400 == state.attributes.get(light.ATTR_COLOR_TEMP)
    assert 153 == state.attributes.get(light.ATTR_MIN_MIREDS)
    assert 500 == state.attributes.get(light.ATTR_MAX_MIREDS)
    assert 'none' == state.attributes.get(light.ATTR_EFFECT)
    common.async_turn_on(hass, ENTITY_LIGHT, kelvin=3000, brightness_pct=50)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_LIGHT)
    assert 333 == state.attributes.get(light.ATTR_COLOR_TEMP)
    assert 127 == state.attributes.get(light.ATTR_BRIGHTNESS)


async def test_turn_off(hass):
    """Test light turn off method."""
    await hass.services.async_call('light', 'turn_on', {
        'entity_id': ENTITY_LIGHT
    }, blocking=True)

    assert light.is_on(hass, ENTITY_LIGHT)

    await hass.services.async_call('light', 'turn_off', {
        'entity_id': ENTITY_LIGHT
    }, blocking=True)

    assert not light.is_on(hass, ENTITY_LIGHT)


async def test_turn_off_without_entity_id(hass):
    """Test light turn off all lights."""
    await hass.services.async_call('light', 'turn_on', {
    }, blocking=True)

    assert light.is_on(hass, ENTITY_LIGHT)

    await hass.services.async_call('light', 'turn_off', {
    }, blocking=True)

    assert not light.is_on(hass, ENTITY_LIGHT)
