"""The tests for the demo light component."""
import pytest

from homeassistant.components import light
from homeassistant.setup import async_setup_component

from tests.components.light import common

ENTITY_LIGHT = "light.bed_light"


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Set up demo component."""
    hass.loop.run_until_complete(
        async_setup_component(hass, light.DOMAIN, {"light": {"platform": "demo"}})
    )


async def test_state_attributes(hass):
    """Test light state attributes."""
    await common.async_turn_on(hass, ENTITY_LIGHT, xy_color=(0.4, 0.4), brightness=25)
    state = hass.states.get(ENTITY_LIGHT)
    assert light.is_on(hass, ENTITY_LIGHT)
    assert (0.4, 0.4) == state.attributes.get(light.ATTR_XY_COLOR)
    assert state.attributes.get(light.ATTR_BRIGHTNESS) == 25
    assert (255, 234, 164) == state.attributes.get(light.ATTR_RGB_COLOR)
    assert state.attributes.get(light.ATTR_EFFECT) == "rainbow"
    await common.async_turn_on(
        hass, ENTITY_LIGHT, rgb_color=(251, 253, 255), white_value=254
    )
    state = hass.states.get(ENTITY_LIGHT)
    assert state.attributes.get(light.ATTR_WHITE_VALUE) == 254
    assert (250, 252, 255) == state.attributes.get(light.ATTR_RGB_COLOR)
    assert (0.319, 0.326) == state.attributes.get(light.ATTR_XY_COLOR)
    await common.async_turn_on(hass, ENTITY_LIGHT, color_temp=400, effect="none")
    state = hass.states.get(ENTITY_LIGHT)
    assert state.attributes.get(light.ATTR_COLOR_TEMP) == 400
    assert state.attributes.get(light.ATTR_MIN_MIREDS) == 153
    assert state.attributes.get(light.ATTR_MAX_MIREDS) == 500
    assert state.attributes.get(light.ATTR_EFFECT) == "none"
    await common.async_turn_on(hass, ENTITY_LIGHT, kelvin=3000, brightness_pct=50)
    state = hass.states.get(ENTITY_LIGHT)
    assert state.attributes.get(light.ATTR_COLOR_TEMP) == 333
    assert state.attributes.get(light.ATTR_BRIGHTNESS) == 127


async def test_turn_off(hass):
    """Test light turn off method."""
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": ENTITY_LIGHT}, blocking=True
    )

    assert light.is_on(hass, ENTITY_LIGHT)

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": ENTITY_LIGHT}, blocking=True
    )

    assert not light.is_on(hass, ENTITY_LIGHT)


async def test_turn_off_without_entity_id(hass):
    """Test light turn off all lights."""
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "all"}, blocking=True
    )

    assert light.is_on(hass, ENTITY_LIGHT)

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "all"}, blocking=True
    )

    assert not light.is_on(hass, ENTITY_LIGHT)
