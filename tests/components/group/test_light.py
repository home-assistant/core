"""The tests for the Group Light platform."""
from unittest.mock import MagicMock

import asynctest

from homeassistant.components.group import DOMAIN
import homeassistant.components.group.light as group
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_MAX_MIREDS,
    ATTR_MIN_MIREDS,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE_VALUE,
    ATTR_XY_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.setup import async_setup_component


async def test_default_state(hass):
    """Test light group default state."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {LIGHT_DOMAIN: {"platform": DOMAIN, "entities": [], "name": "Bedroom Group"}},
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.bedroom_group")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert state.attributes.get(ATTR_BRIGHTNESS) is None
    assert state.attributes.get(ATTR_HS_COLOR) is None
    assert state.attributes.get(ATTR_COLOR_TEMP) is None
    assert state.attributes.get(ATTR_WHITE_VALUE) is None
    assert state.attributes.get(ATTR_EFFECT_LIST) is None
    assert state.attributes.get(ATTR_EFFECT) is None


async def test_state_reporting(hass):
    """Test the state reporting."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["light.test1", "light.test2"],
            }
        },
    )

    hass.states.async_set("light.test1", STATE_ON)
    hass.states.async_set("light.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_ON

    hass.states.async_set("light.test1", STATE_ON)
    hass.states.async_set("light.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_ON

    hass.states.async_set("light.test1", STATE_OFF)
    hass.states.async_set("light.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_OFF

    hass.states.async_set("light.test1", STATE_UNAVAILABLE)
    hass.states.async_set("light.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_UNAVAILABLE


async def test_brightness(hass):
    """Test brightness reporting."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["light.test1", "light.test2"],
            }
        },
    )

    hass.states.async_set(
        "light.test1", STATE_ON, {ATTR_BRIGHTNESS: 255, ATTR_SUPPORTED_FEATURES: 1}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 1
    assert state.attributes[ATTR_BRIGHTNESS] == 255

    hass.states.async_set(
        "light.test2", STATE_ON, {ATTR_BRIGHTNESS: 100, ATTR_SUPPORTED_FEATURES: 1}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 177

    hass.states.async_set(
        "light.test1", STATE_OFF, {ATTR_BRIGHTNESS: 255, ATTR_SUPPORTED_FEATURES: 1}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 1
    assert state.attributes[ATTR_BRIGHTNESS] == 100


async def test_color(hass):
    """Test RGB reporting."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["light.test1", "light.test2"],
            }
        },
    )

    hass.states.async_set(
        "light.test1", STATE_ON, {ATTR_HS_COLOR: (0, 100), ATTR_SUPPORTED_FEATURES: 16}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 16
    assert state.attributes[ATTR_HS_COLOR] == (0, 100)

    hass.states.async_set(
        "light.test2", STATE_ON, {ATTR_HS_COLOR: (0, 50), ATTR_SUPPORTED_FEATURES: 16}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_HS_COLOR] == (0, 75)

    hass.states.async_set(
        "light.test1", STATE_OFF, {ATTR_HS_COLOR: (0, 0), ATTR_SUPPORTED_FEATURES: 16}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_HS_COLOR] == (0, 50)


async def test_white_value(hass):
    """Test white value reporting."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["light.test1", "light.test2"],
            }
        },
    )

    hass.states.async_set(
        "light.test1", STATE_ON, {ATTR_WHITE_VALUE: 255, ATTR_SUPPORTED_FEATURES: 128}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_WHITE_VALUE] == 255

    hass.states.async_set(
        "light.test2", STATE_ON, {ATTR_WHITE_VALUE: 100, ATTR_SUPPORTED_FEATURES: 128}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_WHITE_VALUE] == 177

    hass.states.async_set(
        "light.test1", STATE_OFF, {ATTR_WHITE_VALUE: 255, ATTR_SUPPORTED_FEATURES: 128}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_WHITE_VALUE] == 100


async def test_color_temp(hass):
    """Test color temp reporting."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["light.test1", "light.test2"],
            }
        },
    )

    hass.states.async_set(
        "light.test1", STATE_ON, {"color_temp": 2, ATTR_SUPPORTED_FEATURES: 2}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_TEMP] == 2

    hass.states.async_set(
        "light.test2", STATE_ON, {"color_temp": 1000, ATTR_SUPPORTED_FEATURES: 2}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_TEMP] == 501

    hass.states.async_set(
        "light.test1", STATE_OFF, {"color_temp": 2, ATTR_SUPPORTED_FEATURES: 2}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_TEMP] == 1000


async def test_emulated_color_temp_group(hass):
    """Test emulated color temperature in a group."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": [
                        "light.bed_light",
                        "light.ceiling_lights",
                        "light.kitchen_lights",
                    ],
                },
            ]
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("light.bed_light", STATE_ON, {ATTR_SUPPORTED_FEATURES: 2})
    hass.states.async_set(
        "light.ceiling_lights", STATE_ON, {ATTR_SUPPORTED_FEATURES: 63}
    )
    hass.states.async_set(
        "light.kitchen_lights", STATE_ON, {ATTR_SUPPORTED_FEATURES: 61}
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.light_group", ATTR_COLOR_TEMP: 200},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.bed_light")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_TEMP] == 200
    assert ATTR_HS_COLOR not in state.attributes.keys()

    state = hass.states.get("light.ceiling_lights")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_TEMP] == 200
    assert ATTR_HS_COLOR not in state.attributes.keys()

    state = hass.states.get("light.kitchen_lights")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_HS_COLOR] == (27.001, 19.243)


async def test_min_max_mireds(hass):
    """Test min/max mireds reporting."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["light.test1", "light.test2"],
            }
        },
    )

    hass.states.async_set(
        "light.test1",
        STATE_ON,
        {ATTR_MIN_MIREDS: 2, ATTR_MAX_MIREDS: 5, ATTR_SUPPORTED_FEATURES: 2},
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_MIN_MIREDS] == 2
    assert state.attributes[ATTR_MAX_MIREDS] == 5

    hass.states.async_set(
        "light.test2",
        STATE_ON,
        {ATTR_MIN_MIREDS: 7, ATTR_MAX_MIREDS: 1234567890, ATTR_SUPPORTED_FEATURES: 2},
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_MIN_MIREDS] == 2
    assert state.attributes[ATTR_MAX_MIREDS] == 1234567890

    hass.states.async_set(
        "light.test1",
        STATE_OFF,
        {ATTR_MIN_MIREDS: 1, ATTR_MAX_MIREDS: 2, ATTR_SUPPORTED_FEATURES: 2},
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_MIN_MIREDS] == 1
    assert state.attributes[ATTR_MAX_MIREDS] == 1234567890


async def test_effect_list(hass):
    """Test effect_list reporting."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["light.test1", "light.test2"],
            }
        },
    )

    hass.states.async_set(
        "light.test1",
        STATE_ON,
        {ATTR_EFFECT_LIST: ["None", "Random", "Colorloop"], ATTR_SUPPORTED_FEATURES: 4},
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert set(state.attributes[ATTR_EFFECT_LIST]) == {"None", "Random", "Colorloop"}

    hass.states.async_set(
        "light.test2",
        STATE_ON,
        {ATTR_EFFECT_LIST: ["None", "Random", "Rainbow"], ATTR_SUPPORTED_FEATURES: 4},
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert set(state.attributes[ATTR_EFFECT_LIST]) == {
        "None",
        "Random",
        "Colorloop",
        "Rainbow",
    }

    hass.states.async_set(
        "light.test1",
        STATE_OFF,
        {ATTR_EFFECT_LIST: ["None", "Colorloop", "Seven"], ATTR_SUPPORTED_FEATURES: 4},
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert set(state.attributes[ATTR_EFFECT_LIST]) == {
        "None",
        "Random",
        "Colorloop",
        "Seven",
        "Rainbow",
    }


async def test_effect(hass):
    """Test effect reporting."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["light.test1", "light.test2", "light.test3"],
            }
        },
    )

    hass.states.async_set(
        "light.test1", STATE_ON, {ATTR_EFFECT: "None", ATTR_SUPPORTED_FEATURES: 6}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_EFFECT] == "None"

    hass.states.async_set(
        "light.test2", STATE_ON, {ATTR_EFFECT: "None", ATTR_SUPPORTED_FEATURES: 6}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_EFFECT] == "None"

    hass.states.async_set(
        "light.test3", STATE_ON, {ATTR_EFFECT: "Random", ATTR_SUPPORTED_FEATURES: 6}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_EFFECT] == "None"

    hass.states.async_set(
        "light.test1", STATE_OFF, {ATTR_EFFECT: "None", ATTR_SUPPORTED_FEATURES: 6}
    )
    hass.states.async_set(
        "light.test2", STATE_OFF, {ATTR_EFFECT: "None", ATTR_SUPPORTED_FEATURES: 6}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_EFFECT] == "Random"


async def test_supported_features(hass):
    """Test supported features reporting."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["light.test1", "light.test2"],
            }
        },
    )

    hass.states.async_set("light.test1", STATE_ON, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    hass.states.async_set("light.test2", STATE_ON, {ATTR_SUPPORTED_FEATURES: 2})
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 2

    hass.states.async_set("light.test1", STATE_OFF, {ATTR_SUPPORTED_FEATURES: 41})
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 43

    hass.states.async_set("light.test2", STATE_OFF, {ATTR_SUPPORTED_FEATURES: 256})
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 41


async def test_service_calls(hass):
    """Test service calls."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": [
                        "light.bed_light",
                        "light.ceiling_lights",
                        "light.kitchen_lights",
                    ],
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get("light.light_group").state == STATE_ON
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "light.light_group"},
        blocking=True,
    )

    assert hass.states.get("light.bed_light").state == STATE_OFF
    assert hass.states.get("light.ceiling_lights").state == STATE_OFF
    assert hass.states.get("light.kitchen_lights").state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.light_group"},
        blocking=True,
    )

    assert hass.states.get("light.bed_light").state == STATE_ON
    assert hass.states.get("light.ceiling_lights").state == STATE_ON
    assert hass.states.get("light.kitchen_lights").state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.light_group"},
        blocking=True,
    )

    assert hass.states.get("light.bed_light").state == STATE_OFF
    assert hass.states.get("light.ceiling_lights").state == STATE_OFF
    assert hass.states.get("light.kitchen_lights").state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.light_group",
            ATTR_BRIGHTNESS: 128,
            ATTR_EFFECT: "Random",
            ATTR_RGB_COLOR: (42, 255, 255),
        },
        blocking=True,
    )

    state = hass.states.get("light.bed_light")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_EFFECT] == "Random"
    assert state.attributes[ATTR_RGB_COLOR] == (42, 255, 255)

    state = hass.states.get("light.ceiling_lights")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_EFFECT] == "Random"
    assert state.attributes[ATTR_RGB_COLOR] == (42, 255, 255)

    state = hass.states.get("light.kitchen_lights")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_EFFECT] == "Random"
    assert state.attributes[ATTR_RGB_COLOR] == (42, 255, 255)


async def test_invalid_service_calls(hass):
    """Test invalid service call arguments get discarded."""
    add_entities = MagicMock()
    await group.async_setup_platform(
        hass, {"entities": ["light.test1", "light.test2"]}, add_entities
    )

    assert add_entities.call_count == 1
    grouped_light = add_entities.call_args[0][0][0]
    grouped_light.hass = hass

    with asynctest.patch.object(hass.services, "async_call") as mock_call:
        await grouped_light.async_turn_on(brightness=150, four_oh_four="404")
        data = {ATTR_ENTITY_ID: ["light.test1", "light.test2"], ATTR_BRIGHTNESS: 150}
        mock_call.assert_called_once_with(
            LIGHT_DOMAIN, SERVICE_TURN_ON, data, blocking=True
        )
        mock_call.reset_mock()

        await grouped_light.async_turn_off(transition=4, four_oh_four="404")
        data = {ATTR_ENTITY_ID: ["light.test1", "light.test2"], ATTR_TRANSITION: 4}
        mock_call.assert_called_once_with(
            LIGHT_DOMAIN, SERVICE_TURN_OFF, data, blocking=True
        )
        mock_call.reset_mock()

        data = {
            ATTR_BRIGHTNESS: 150,
            ATTR_XY_COLOR: (0.5, 0.42),
            ATTR_RGB_COLOR: (80, 120, 50),
            ATTR_COLOR_TEMP: 1234,
            ATTR_WHITE_VALUE: 1,
            ATTR_EFFECT: "Sunshine",
            ATTR_TRANSITION: 4,
            ATTR_FLASH: "long",
        }
        await grouped_light.async_turn_on(**data)
        data[ATTR_ENTITY_ID] = ["light.test1", "light.test2"]
        data.pop(ATTR_RGB_COLOR)
        data.pop(ATTR_XY_COLOR)
        mock_call.assert_called_once_with(
            LIGHT_DOMAIN, SERVICE_TURN_ON, data, blocking=True
        )
