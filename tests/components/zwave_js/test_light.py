"""Test the Z-Wave JS light platform."""
from homeassistant.components.light import ATTR_MAX_MIREDS, ATTR_MIN_MIREDS
from homeassistant.const import ATTR_SUPPORTED_FEATURES, STATE_OFF

BULB_6_MULTI_COLOR_LIGHT = "light.bulb_6_multi_color_current_value"


async def test_light(hass, bulb_6_multi_color, integration):
    """Test the light entity."""
    state = hass.states.get(BULB_6_MULTI_COLOR_LIGHT)

    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_MIN_MIREDS] == 153
    assert state.attributes[ATTR_MAX_MIREDS] == 370
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 51
