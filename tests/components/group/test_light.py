"""The tests for the Group Light platform."""
from os import path
import unittest.mock
from unittest.mock import MagicMock, patch

from homeassistant import config as hass_config
from homeassistant.components.group import DOMAIN, SERVICE_RELOAD
import homeassistant.components.group.light as group
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_MAX_MIREDS,
    ATTR_MIN_MIREDS,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ATTR_WHITE_VALUE,
    ATTR_XY_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component


async def test_default_state(hass):
    """Test light group default state."""
    hass.states.async_set("light.kitchen", "on")
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["light.kitchen", "light.bedroom"],
                "name": "Bedroom Group",
                "unique_id": "unique_identifier",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.bedroom_group")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert state.attributes.get(ATTR_ENTITY_ID) == ["light.kitchen", "light.bedroom"]
    assert state.attributes.get(ATTR_BRIGHTNESS) is None
    assert state.attributes.get(ATTR_HS_COLOR) is None
    assert state.attributes.get(ATTR_COLOR_TEMP) is None
    assert state.attributes.get(ATTR_WHITE_VALUE) is None
    assert state.attributes.get(ATTR_EFFECT_LIST) is None
    assert state.attributes.get(ATTR_EFFECT) is None

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("light.bedroom_group")
    assert entry
    assert entry.unique_id == "unique_identifier"


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
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

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


async def test_brightness(hass, enable_custom_integrations):
    """Test brightness reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {COLOR_MODE_BRIGHTNESS}
    entity0.color_mode = COLOR_MODE_BRIGHTNESS
    entity0.brightness = 255

    entity1 = platform.ENTITIES[1]
    entity1.supported_features = SUPPORT_BRIGHTNESS

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": ["light.test1", "light.test2"],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.light_group")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 255
    assert state.attributes[ATTR_COLOR_MODE] == "brightness"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["brightness"]

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": [entity1.entity_id], ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 177
    assert state.attributes[ATTR_COLOR_MODE] == "brightness"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["brightness"]

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": [entity0.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 100
    assert state.attributes[ATTR_COLOR_MODE] == "brightness"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["brightness"]


async def test_color_hs(hass, enable_custom_integrations):
    """Test hs color reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {COLOR_MODE_HS}
    entity0.color_mode = COLOR_MODE_HS
    entity0.brightness = 255
    entity0.hs_color = (0, 100)

    entity1 = platform.ENTITIES[1]
    entity1.supported_features = SUPPORT_COLOR

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": ["light.test1", "light.test2"],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.light_group")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == "hs"
    assert state.attributes[ATTR_HS_COLOR] == (0, 100)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["hs"]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": [entity1.entity_id], ATTR_HS_COLOR: (0, 50)},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == "hs"
    assert state.attributes[ATTR_HS_COLOR] == (0, 75)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["hs"]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": [entity0.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == "hs"
    assert state.attributes[ATTR_HS_COLOR] == (0, 50)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["hs"]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0


async def test_color_rgbw(hass, enable_custom_integrations):
    """Test rgbw color reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {COLOR_MODE_RGBW}
    entity0.color_mode = COLOR_MODE_RGBW
    entity0.brightness = 255
    entity0.rgbw_color = (0, 64, 128, 255)

    entity1 = platform.ENTITIES[1]
    entity1.supported_color_modes = {COLOR_MODE_RGBW}
    entity1.color_mode = COLOR_MODE_RGBW
    entity1.brightness = 255
    entity1.rgbw_color = (255, 128, 64, 0)

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": ["light.test1", "light.test2"],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.light_group")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == "rgbw"
    assert state.attributes[ATTR_RGBW_COLOR] == (0, 64, 128, 255)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgbw"]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": [entity1.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == "rgbw"
    assert state.attributes[ATTR_RGBW_COLOR] == (127, 96, 96, 127)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgbw"]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": [entity0.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == "rgbw"
    assert state.attributes[ATTR_RGBW_COLOR] == (255, 128, 64, 0)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgbw"]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0


async def test_color_rgbww(hass, enable_custom_integrations):
    """Test rgbww color reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {COLOR_MODE_RGBWW}
    entity0.color_mode = COLOR_MODE_RGBWW
    entity0.brightness = 255
    entity0.rgbww_color = (0, 32, 64, 128, 255)

    entity1 = platform.ENTITIES[1]
    entity1.supported_color_modes = {COLOR_MODE_RGBWW}
    entity1.color_mode = COLOR_MODE_RGBWW
    entity1.brightness = 255
    entity1.rgbww_color = (255, 128, 64, 32, 0)

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": ["light.test1", "light.test2"],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.light_group")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == "rgbww"
    assert state.attributes[ATTR_RGBWW_COLOR] == (0, 32, 64, 128, 255)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgbww"]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": [entity1.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == "rgbww"
    assert state.attributes[ATTR_RGBWW_COLOR] == (127, 80, 64, 80, 127)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgbww"]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": [entity0.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == "rgbww"
    assert state.attributes[ATTR_RGBWW_COLOR] == (255, 128, 64, 32, 0)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgbww"]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0


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
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set(
        "light.test1", STATE_ON, {ATTR_WHITE_VALUE: 255, ATTR_SUPPORTED_FEATURES: 128}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 128
    assert state.attributes[ATTR_WHITE_VALUE] == 255

    hass.states.async_set(
        "light.test2", STATE_ON, {ATTR_WHITE_VALUE: 100, ATTR_SUPPORTED_FEATURES: 128}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 128
    assert state.attributes[ATTR_WHITE_VALUE] == 177

    hass.states.async_set(
        "light.test1", STATE_OFF, {ATTR_WHITE_VALUE: 255, ATTR_SUPPORTED_FEATURES: 128}
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 128
    assert state.attributes[ATTR_WHITE_VALUE] == 100


async def test_color_temp(hass, enable_custom_integrations):
    """Test color temp reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {COLOR_MODE_COLOR_TEMP}
    entity0.color_mode = COLOR_MODE_COLOR_TEMP
    entity0.brightness = 255
    entity0.color_temp = 2

    entity1 = platform.ENTITIES[1]
    entity1.supported_features = SUPPORT_COLOR_TEMP

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": ["light.test1", "light.test2"],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == "color_temp"
    assert state.attributes[ATTR_COLOR_TEMP] == 2
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp"]

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": [entity1.entity_id], ATTR_COLOR_TEMP: 1000},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == "color_temp"
    assert state.attributes[ATTR_COLOR_TEMP] == 501
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp"]

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": [entity0.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == "color_temp"
    assert state.attributes[ATTR_COLOR_TEMP] == 1000
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp"]


async def test_emulated_color_temp_group(hass, enable_custom_integrations):
    """Test emulated color temperature in a group."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))
    platform.ENTITIES.append(platform.MockLight("test3", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {COLOR_MODE_COLOR_TEMP}
    entity0.color_mode = COLOR_MODE_COLOR_TEMP

    entity1 = platform.ENTITIES[1]
    entity1.supported_color_modes = {COLOR_MODE_COLOR_TEMP, COLOR_MODE_HS}
    entity1.color_mode = COLOR_MODE_COLOR_TEMP

    entity2 = platform.ENTITIES[2]
    entity2.supported_color_modes = {COLOR_MODE_HS}
    entity2.color_mode = COLOR_MODE_HS

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": ["light.test1", "light.test2", "light.test3"],
                },
            ]
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    await hass.async_block_till_done()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.light_group", ATTR_COLOR_TEMP: 200},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.test1")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_TEMP] == 200
    assert ATTR_HS_COLOR not in state.attributes.keys()

    state = hass.states.get("light.test2")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_TEMP] == 200
    assert ATTR_HS_COLOR not in state.attributes.keys()

    state = hass.states.get("light.test3")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_HS_COLOR] == (27.001, 19.243)


async def test_min_max_mireds(hass, enable_custom_integrations):
    """Test min/max mireds reporting.

    min/max mireds is reported both when light is on and off
    """
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {COLOR_MODE_COLOR_TEMP}
    entity0.color_mode = COLOR_MODE_COLOR_TEMP
    entity0.color_temp = 2
    entity0.min_mireds = 2
    entity0.max_mireds = 5

    entity1 = platform.ENTITIES[1]
    entity1.supported_features = SUPPORT_COLOR_TEMP
    entity1.min_mireds = 1
    entity1.max_mireds = 1234567890

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": ["light.test1", "light.test2"],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_MIN_MIREDS] == 1
    assert state.attributes[ATTR_MAX_MIREDS] == 1234567890

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": [entity0.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_MIN_MIREDS] == 1
    assert state.attributes[ATTR_MAX_MIREDS] == 1234567890

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": [entity0.entity_id]},
        blocking=True,
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
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set(
        "light.test1",
        STATE_ON,
        {ATTR_EFFECT_LIST: ["None", "Random", "Colorloop"], ATTR_SUPPORTED_FEATURES: 4},
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert set(state.attributes[ATTR_EFFECT_LIST]) == {"None", "Random", "Colorloop"}
    # These ensure the output is sorted as expected
    assert state.attributes[ATTR_EFFECT_LIST][0] == "None"
    assert state.attributes[ATTR_EFFECT_LIST][1] == "Colorloop"
    assert state.attributes[ATTR_EFFECT_LIST][2] == "Random"

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
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

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


async def test_supported_color_modes(hass, enable_custom_integrations):
    """Test supported_color_modes reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))
    platform.ENTITIES.append(platform.MockLight("test3", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {COLOR_MODE_COLOR_TEMP, COLOR_MODE_HS}

    entity1 = platform.ENTITIES[1]
    entity1.supported_color_modes = {COLOR_MODE_RGBW, COLOR_MODE_RGBWW}

    entity2 = platform.ENTITIES[2]
    entity2.supported_features = SUPPORT_BRIGHTNESS

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": ["light.test1", "light.test2", "light.test3"],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.light_group")
    assert set(state.attributes[ATTR_SUPPORTED_COLOR_MODES]) == {
        "brightness",
        "color_temp",
        "hs",
        "rgbw",
        "rgbww",
    }


async def test_color_mode(hass, enable_custom_integrations):
    """Test color_mode reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))
    platform.ENTITIES.append(platform.MockLight("test3", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {COLOR_MODE_COLOR_TEMP, COLOR_MODE_HS}
    entity0.color_mode = COLOR_MODE_COLOR_TEMP

    entity1 = platform.ENTITIES[1]
    entity1.supported_color_modes = {COLOR_MODE_COLOR_TEMP, COLOR_MODE_HS}
    entity1.color_mode = COLOR_MODE_COLOR_TEMP

    entity2 = platform.ENTITIES[2]
    entity2.supported_color_modes = {COLOR_MODE_COLOR_TEMP, COLOR_MODE_HS}
    entity2.color_mode = COLOR_MODE_HS

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": ["light.test1", "light.test2", "light.test3"],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == COLOR_MODE_COLOR_TEMP

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": [entity1.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == COLOR_MODE_COLOR_TEMP

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": [entity2.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == COLOR_MODE_COLOR_TEMP

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": [entity0.entity_id, entity1.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == COLOR_MODE_HS


async def test_color_mode2(hass, enable_custom_integrations):
    """Test onoff color_mode and brightness are given lowest priority."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test3", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test4", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test5", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test6", STATE_ON))

    entity = platform.ENTITIES[0]
    entity.supported_color_modes = {COLOR_MODE_COLOR_TEMP}
    entity.color_mode = COLOR_MODE_COLOR_TEMP

    entity = platform.ENTITIES[1]
    entity.supported_color_modes = {COLOR_MODE_BRIGHTNESS}
    entity.color_mode = COLOR_MODE_BRIGHTNESS

    entity = platform.ENTITIES[2]
    entity.supported_color_modes = {COLOR_MODE_BRIGHTNESS}
    entity.color_mode = COLOR_MODE_BRIGHTNESS

    entity = platform.ENTITIES[3]
    entity.supported_color_modes = {COLOR_MODE_ONOFF}
    entity.color_mode = COLOR_MODE_ONOFF

    entity = platform.ENTITIES[4]
    entity.supported_color_modes = {COLOR_MODE_ONOFF}
    entity.color_mode = COLOR_MODE_ONOFF

    entity = platform.ENTITIES[5]
    entity.supported_color_modes = {COLOR_MODE_ONOFF}
    entity.color_mode = COLOR_MODE_ONOFF

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": [
                        "light.test1",
                        "light.test2",
                        "light.test3",
                        "light.test4",
                        "light.test5",
                        "light.test6",
                    ],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == COLOR_MODE_COLOR_TEMP

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": ["light.test1"]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == COLOR_MODE_BRIGHTNESS


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
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("light.test1", STATE_ON, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    # SUPPORT_COLOR_TEMP = 2
    # SUPPORT_COLOR_TEMP = 2 will be blocked in favour of COLOR_MODE_COLOR_TEMP
    hass.states.async_set("light.test2", STATE_ON, {ATTR_SUPPORTED_FEATURES: 2})
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    # SUPPORT_TRANSITION | SUPPORT_FLASH | SUPPORT_BRIGHTNESS = 41
    # SUPPORT_BRIGHTNESS = 1 will be translated to COLOR_MODE_BRIGHTNESS
    hass.states.async_set("light.test1", STATE_OFF, {ATTR_SUPPORTED_FEATURES: 41})
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    # SUPPORT_TRANSITION | SUPPORT_FLASH = 40
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 40

    # Test that unknown feature 256 is blocked
    hass.states.async_set("light.test2", STATE_OFF, {ATTR_SUPPORTED_FEATURES: 256})
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 40


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
    await hass.async_start()
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
    assert state.attributes[ATTR_RGB_COLOR] == (42, 255, 255)

    state = hass.states.get("light.kitchen_lights")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_RGB_COLOR] == (42, 255, 255)


async def test_invalid_service_calls(hass):
    """Test invalid service call arguments get discarded."""
    add_entities = MagicMock()
    await group.async_setup_platform(
        hass, {"name": "test", "entities": ["light.test1", "light.test2"]}, add_entities
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert add_entities.call_count == 1
    grouped_light = add_entities.call_args[0][0][0]
    grouped_light.hass = hass

    with unittest.mock.patch.object(hass.services, "async_call") as mock_call:
        await grouped_light.async_turn_on(brightness=150, four_oh_four="404")
        data = {ATTR_ENTITY_ID: ["light.test1", "light.test2"], ATTR_BRIGHTNESS: 150}
        mock_call.assert_called_once_with(
            LIGHT_DOMAIN, SERVICE_TURN_ON, data, blocking=True, context=None
        )
        mock_call.reset_mock()

        await grouped_light.async_turn_off(transition=4, four_oh_four="404")
        data = {ATTR_ENTITY_ID: ["light.test1", "light.test2"], ATTR_TRANSITION: 4}
        mock_call.assert_called_once_with(
            LIGHT_DOMAIN, SERVICE_TURN_OFF, data, blocking=True, context=None
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
        mock_call.assert_called_once_with(
            LIGHT_DOMAIN, SERVICE_TURN_ON, data, blocking=True, context=None
        )


async def test_reload(hass):
    """Test the ability to reload lights."""
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

    await hass.async_block_till_done()
    await hass.async_start()

    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_ON

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "group/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("light.light_group") is None
    assert hass.states.get("light.master_hall_lights_g") is not None
    assert hass.states.get("light.outside_patio_lights_g") is not None


async def test_reload_with_platform_not_setup(hass):
    """Test the ability to reload lights."""
    hass.states.async_set("light.bowl", STATE_ON)
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "demo"},
            ]
        },
    )
    assert await async_setup_component(
        hass,
        "group",
        {
            "group": {
                "group_zero": {"entities": "light.Bowl", "icon": "mdi:work"},
            }
        },
    )
    await hass.async_block_till_done()

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "group/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("light.light_group") is None
    assert hass.states.get("light.master_hall_lights_g") is not None
    assert hass.states.get("light.outside_patio_lights_g") is not None


async def test_reload_with_base_integration_platform_not_setup(hass):
    """Test the ability to reload lights."""
    assert await async_setup_component(
        hass,
        "group",
        {
            "group": {
                "group_zero": {"entities": "light.Bowl", "icon": "mdi:work"},
            }
        },
    )
    await hass.async_block_till_done()
    hass.states.async_set("light.master_hall_lights", STATE_ON)
    hass.states.async_set("light.master_hall_lights_2", STATE_OFF)

    hass.states.async_set("light.outside_patio_lights", STATE_OFF)
    hass.states.async_set("light.outside_patio_lights_2", STATE_OFF)

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "group/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("light.light_group") is None
    assert hass.states.get("light.master_hall_lights_g") is not None
    assert hass.states.get("light.outside_patio_lights_g") is not None
    assert hass.states.get("light.master_hall_lights_g").state == STATE_ON
    assert hass.states.get("light.outside_patio_lights_g").state == STATE_OFF


async def test_nested_group(hass):
    """Test nested light group."""
    hass.states.async_set("light.kitchen", "on")
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {
                    "platform": DOMAIN,
                    "entities": ["light.bedroom_group"],
                    "name": "Nested Group",
                },
                {
                    "platform": DOMAIN,
                    "entities": ["light.kitchen", "light.bedroom"],
                    "name": "Bedroom Group",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.bedroom_group")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ENTITY_ID) == ["light.kitchen", "light.bedroom"]

    state = hass.states.get("light.nested_group")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ENTITY_ID) == ["light.bedroom_group"]


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))
