"""The scene tests for the myq platform."""
from homeassistant.components.light import ColorMode
from homeassistant.const import STATE_OFF, STATE_ON

from .util import async_init_integration


async def test_create_lights(hass):
    """Test creation of lights."""

    await async_init_integration(hass)

    state = hass.states.get("light.garage_door_light_off")
    assert state.state == STATE_OFF
    expected_attributes = {
        "friendly_name": "Garage Door Light Off",
        "supported_features": 0,
        "supported_color_modes": [ColorMode.ONOFF],
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == expected_attributes[key] for key in expected_attributes
    )

    state = hass.states.get("light.garage_door_light_on")
    assert state.state == STATE_ON
    expected_attributes = {
        "friendly_name": "Garage Door Light On",
        "supported_features": 0,
        "supported_color_modes": [ColorMode.ONOFF],
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears

    assert all(
        state.attributes[key] == expected_attributes[key] for key in expected_attributes
    )
