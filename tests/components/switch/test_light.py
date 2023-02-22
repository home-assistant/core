"""The tests for the Light Switch platform."""
from homeassistant.components.light import (
    ATTR_COLOR_MODE,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import common as switch_common

from tests.components.light import common


async def test_default_state(hass: HomeAssistant) -> None:
    """Test light switch default state."""
    await async_setup_component(
        hass,
        "light",
        {
            "light": {
                "platform": "switch",
                "entity_id": "switch.test",
                "name": "Christmas Tree Lights",
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.christmas_tree_lights")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes["supported_features"] == 0
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("effect_list") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) == [ColorMode.ONOFF]
    assert state.attributes.get(ATTR_COLOR_MODE) is None


async def test_light_service_calls(hass: HomeAssistant) -> None:
    """Test service calls to light."""
    await async_setup_component(hass, "switch", {"switch": [{"platform": "demo"}]})
    await async_setup_component(
        hass,
        "light",
        {"light": [{"platform": "switch", "entity_id": "switch.decorative_lights"}]},
    )
    await hass.async_block_till_done()

    assert hass.states.get("light.light_switch").state == "on"

    await common.async_toggle(hass, "light.light_switch")

    assert hass.states.get("switch.decorative_lights").state == "off"
    assert hass.states.get("light.light_switch").state == "off"

    await common.async_turn_on(hass, "light.light_switch")

    assert hass.states.get("switch.decorative_lights").state == "on"
    assert hass.states.get("light.light_switch").state == "on"
    assert (
        hass.states.get("light.light_switch").attributes.get(ATTR_COLOR_MODE)
        == ColorMode.ONOFF
    )

    await common.async_turn_off(hass, "light.light_switch")
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == "off"
    assert hass.states.get("light.light_switch").state == "off"


async def test_switch_service_calls(hass: HomeAssistant) -> None:
    """Test service calls to switch."""
    await async_setup_component(hass, "switch", {"switch": [{"platform": "demo"}]})
    await async_setup_component(
        hass,
        "light",
        {"light": [{"platform": "switch", "entity_id": "switch.decorative_lights"}]},
    )
    await hass.async_block_till_done()

    assert hass.states.get("light.light_switch").state == "on"

    await switch_common.async_turn_off(hass, "switch.decorative_lights")
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == "off"
    assert hass.states.get("light.light_switch").state == "off"

    await switch_common.async_turn_on(hass, "switch.decorative_lights")
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == "on"
    assert hass.states.get("light.light_switch").state == "on"
