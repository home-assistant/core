"""The tests for the Group Light platform."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config as hass_config
from homeassistant.components.group import DOMAIN, SERVICE_RELOAD
import homeassistant.components.group.light as group
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_NAME,
    ATTR_COLOR_TEMP,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ATTR_WHITE,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    EVENT_CALL_SERVICE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import async_capture_events, get_fixture_path


async def test_default_state(hass: HomeAssistant) -> None:
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
                "all": "false",
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
    assert state.attributes.get(ATTR_COLOR_TEMP_KELVIN) is None
    assert state.attributes.get(ATTR_EFFECT_LIST) is None
    assert state.attributes.get(ATTR_EFFECT) is None

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("light.bedroom_group")
    assert entry
    assert entry.unique_id == "unique_identifier"


async def test_state_reporting_any(hass: HomeAssistant) -> None:
    """Test the state reporting in 'any' mode.

    The group state is unavailable if all group members are unavailable.
    Otherwise, the group state is unknown if all group members are unknown.
    Otherwise, the group state is on if at least one group member is on.
    Otherwise, the group state is off.
    """
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["light.test1", "light.test2"],
                "all": "false",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Initial state with no group member in the state machine -> unavailable
    assert hass.states.get("light.light_group").state == STATE_UNAVAILABLE

    # All group members unavailable -> unavailable
    hass.states.async_set("light.test1", STATE_UNAVAILABLE)
    hass.states.async_set("light.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_UNAVAILABLE

    # All group members unknown -> unknown
    hass.states.async_set("light.test1", STATE_UNKNOWN)
    hass.states.async_set("light.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_UNKNOWN

    # Group members unknown or unavailable -> unknown
    hass.states.async_set("light.test1", STATE_UNKNOWN)
    hass.states.async_set("light.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_UNKNOWN

    # At least one member on -> group on
    hass.states.async_set("light.test1", STATE_ON)
    hass.states.async_set("light.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_ON

    hass.states.async_set("light.test1", STATE_ON)
    hass.states.async_set("light.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_ON

    hass.states.async_set("light.test1", STATE_ON)
    hass.states.async_set("light.test2", STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_ON

    hass.states.async_set("light.test1", STATE_ON)
    hass.states.async_set("light.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_ON

    # Otherwise -> off
    hass.states.async_set("light.test1", STATE_OFF)
    hass.states.async_set("light.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_OFF

    hass.states.async_set("light.test1", STATE_UNKNOWN)
    hass.states.async_set("light.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_OFF

    hass.states.async_set("light.test1", STATE_UNAVAILABLE)
    hass.states.async_set("light.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_OFF

    # All group members removed from the state machine -> unavailable
    hass.states.async_remove("light.test1")
    hass.states.async_remove("light.test2")
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_UNAVAILABLE


async def test_state_reporting_all(hass: HomeAssistant) -> None:
    """Test the state reporting in 'all' mode.

    The group state is unavailable if all group members are unavailable.
    Otherwise, the group state is unknown if at least one group member is unknown or unavailable.
    Otherwise, the group state is off if at least one group member is off.
    Otherwise, the group state is on.
    """
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["light.test1", "light.test2"],
                "all": "true",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Initial state with no group member in the state machine -> unavailable
    assert hass.states.get("light.light_group").state == STATE_UNAVAILABLE

    # All group members unavailable -> unavailable
    hass.states.async_set("light.test1", STATE_UNAVAILABLE)
    hass.states.async_set("light.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_UNAVAILABLE

    # At least one member unknown or unavailable -> group unknown
    hass.states.async_set("light.test1", STATE_ON)
    hass.states.async_set("light.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_UNKNOWN

    hass.states.async_set("light.test1", STATE_ON)
    hass.states.async_set("light.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_UNKNOWN

    hass.states.async_set("light.test1", STATE_UNKNOWN)
    hass.states.async_set("light.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_UNKNOWN

    hass.states.async_set("light.test1", STATE_OFF)
    hass.states.async_set("light.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_UNKNOWN

    hass.states.async_set("light.test1", STATE_OFF)
    hass.states.async_set("light.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_UNKNOWN

    hass.states.async_set("binary_sensor.test1", STATE_UNKNOWN)
    hass.states.async_set("binary_sensor.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_UNKNOWN

    # At least one member off -> group off
    hass.states.async_set("light.test1", STATE_ON)
    hass.states.async_set("light.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_OFF

    hass.states.async_set("light.test1", STATE_OFF)
    hass.states.async_set("light.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_OFF

    # Otherwise -> on
    hass.states.async_set("light.test1", STATE_ON)
    hass.states.async_set("light.test2", STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_ON

    # All group members removed from the state machine -> unavailable
    hass.states.async_remove("light.test1")
    hass.states.async_remove("light.test2")
    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_UNAVAILABLE


async def test_brightness(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test brightness reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {ColorMode.BRIGHTNESS}
    entity0.color_mode = ColorMode.BRIGHTNESS
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
                    "all": "false",
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


async def test_color_hs(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    """Test hs color reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {ColorMode.HS}
    entity0.color_mode = ColorMode.HS
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
                    "all": "false",
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


async def test_color_rgb(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    """Test rgbw color reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {ColorMode.RGB}
    entity0.color_mode = ColorMode.RGB
    entity0.brightness = 255
    entity0.rgb_color = (0, 64, 128)

    entity1 = platform.ENTITIES[1]
    entity1.supported_color_modes = {ColorMode.RGB}
    entity1.color_mode = ColorMode.RGB
    entity1.brightness = 255
    entity1.rgb_color = (255, 128, 64)

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": ["light.test1", "light.test2"],
                    "all": "false",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.light_group")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == "rgb"
    assert state.attributes[ATTR_RGB_COLOR] == (0, 64, 128)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgb"]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": [entity1.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == "rgb"
    assert state.attributes[ATTR_RGB_COLOR] == (127, 96, 96)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgb"]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": [entity0.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == "rgb"
    assert state.attributes[ATTR_RGB_COLOR] == (255, 128, 64)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["rgb"]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0


async def test_color_rgbw(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test rgbw color reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {ColorMode.RGBW}
    entity0.color_mode = ColorMode.RGBW
    entity0.brightness = 255
    entity0.rgbw_color = (0, 64, 128, 255)

    entity1 = platform.ENTITIES[1]
    entity1.supported_color_modes = {ColorMode.RGBW}
    entity1.color_mode = ColorMode.RGBW
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
                    "all": "false",
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


async def test_color_rgbww(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test rgbww color reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {ColorMode.RGBWW}
    entity0.color_mode = ColorMode.RGBWW
    entity0.brightness = 255
    entity0.rgbww_color = (0, 32, 64, 128, 255)

    entity1 = platform.ENTITIES[1]
    entity1.supported_color_modes = {ColorMode.RGBWW}
    entity1.color_mode = ColorMode.RGBWW
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
                    "all": "false",
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


async def test_white(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    """Test white reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_ON))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {ColorMode.HS, ColorMode.WHITE}
    entity0.color_mode = ColorMode.WHITE
    entity0.brightness = 255

    entity1 = platform.ENTITIES[1]
    entity1.supported_color_modes = {ColorMode.HS, ColorMode.WHITE}
    entity1.color_mode = ColorMode.WHITE
    entity1.brightness = 128

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": ["light.test1", "light.test2"],
                    "all": "false",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == "white"
    assert state.attributes[ATTR_BRIGHTNESS] == 191
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["hs", "white"]

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": ["light.light_group"], ATTR_WHITE: 128},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == "white"
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["hs", "white"]


async def test_color_temp(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test color temp reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {ColorMode.COLOR_TEMP}
    entity0.color_mode = ColorMode.COLOR_TEMP
    entity0.brightness = 255
    entity0.color_temp_kelvin = 2

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
                    "all": "false",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == "color_temp"
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 2
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp"]

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": [entity1.entity_id], ATTR_COLOR_TEMP_KELVIN: 1000},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == "color_temp"
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 501
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
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 1000
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp"]


async def test_emulated_color_temp_group(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test emulated color temperature in a group."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))
    platform.ENTITIES.append(platform.MockLight("test3", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {ColorMode.COLOR_TEMP}
    entity0.color_mode = ColorMode.COLOR_TEMP

    entity1 = platform.ENTITIES[1]
    entity1.supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}
    entity1.color_mode = ColorMode.COLOR_TEMP

    entity2 = platform.ENTITIES[2]
    entity2.supported_color_modes = {ColorMode.HS}
    entity2.color_mode = ColorMode.HS

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": ["light.test1", "light.test2", "light.test3"],
                    "all": "false",
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
    assert ATTR_HS_COLOR in state.attributes

    state = hass.states.get("light.test2")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_TEMP] == 200
    assert ATTR_HS_COLOR in state.attributes

    state = hass.states.get("light.test3")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_HS_COLOR] == (27.001, 19.243)


async def test_min_max_mireds(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test min/max mireds reporting.

    min/max mireds is reported both when light is on and off
    """
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {ColorMode.COLOR_TEMP}
    entity0.color_mode = ColorMode.COLOR_TEMP
    entity0.color_temp_kelvin = 2
    entity0._attr_min_color_temp_kelvin = 2
    entity0._attr_max_color_temp_kelvin = 5

    entity1 = platform.ENTITIES[1]
    entity1.supported_features = SUPPORT_COLOR_TEMP
    entity1._attr_min_color_temp_kelvin = 1
    entity1._attr_max_color_temp_kelvin = 1234567890

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": ["light.test1", "light.test2"],
                    "all": "false",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 1
    assert state.attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 1234567890

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": [entity0.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 1
    assert state.attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 1234567890

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": [entity0.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 1
    assert state.attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 1234567890


async def test_effect_list(hass: HomeAssistant) -> None:
    """Test effect_list reporting."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["light.test1", "light.test2"],
                "all": "false",
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


async def test_effect(hass: HomeAssistant) -> None:
    """Test effect reporting."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["light.test1", "light.test2", "light.test3"],
                "all": "false",
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


async def test_supported_color_modes(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test supported_color_modes reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))
    platform.ENTITIES.append(platform.MockLight("test3", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}

    entity1 = platform.ENTITIES[1]
    entity1.supported_color_modes = {ColorMode.RGBW, ColorMode.RGBWW}

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
                    "all": "false",
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


async def test_color_mode(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test color_mode reporting."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("test1", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("test2", STATE_OFF))
    platform.ENTITIES.append(platform.MockLight("test3", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}
    entity0.color_mode = ColorMode.COLOR_TEMP

    entity1 = platform.ENTITIES[1]
    entity1.supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}
    entity1.color_mode = ColorMode.COLOR_TEMP

    entity2 = platform.ENTITIES[2]
    entity2.supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}
    entity2.color_mode = ColorMode.HS

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": ["light.test1", "light.test2", "light.test3"],
                    "all": "false",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": [entity1.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": [entity2.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": [entity0.entity_id, entity1.entity_id]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.HS


async def test_color_mode2(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
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
    entity.supported_color_modes = {ColorMode.COLOR_TEMP}
    entity.color_mode = ColorMode.COLOR_TEMP

    entity = platform.ENTITIES[1]
    entity.supported_color_modes = {ColorMode.BRIGHTNESS}
    entity.color_mode = ColorMode.BRIGHTNESS

    entity = platform.ENTITIES[2]
    entity.supported_color_modes = {ColorMode.BRIGHTNESS}
    entity.color_mode = ColorMode.BRIGHTNESS

    entity = platform.ENTITIES[3]
    entity.supported_color_modes = {ColorMode.ONOFF}
    entity.color_mode = ColorMode.ONOFF

    entity = platform.ENTITIES[4]
    entity.supported_color_modes = {ColorMode.ONOFF}
    entity.color_mode = ColorMode.ONOFF

    entity = platform.ENTITIES[5]
    entity.supported_color_modes = {ColorMode.ONOFF}
    entity.color_mode = ColorMode.ONOFF

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
                    "all": "false",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": ["light.test1"]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS


async def test_supported_features(hass: HomeAssistant) -> None:
    """Test supported features reporting."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["light.test1", "light.test2"],
                "all": "false",
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
    # SUPPORT_COLOR_TEMP = 2 will be blocked in favour of ColorMode.COLOR_TEMP
    hass.states.async_set("light.test2", STATE_ON, {ATTR_SUPPORTED_FEATURES: 2})
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    # LightEntityFeature.TRANSITION | LightEntityFeature.FLASH | SUPPORT_BRIGHTNESS = 41
    # SUPPORT_BRIGHTNESS = 1 will be translated to ColorMode.BRIGHTNESS
    hass.states.async_set("light.test1", STATE_OFF, {ATTR_SUPPORTED_FEATURES: 41})
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    # LightEntityFeature.TRANSITION | LightEntityFeature.FLASH = 40
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 40

    # Test that unknown feature 256 is blocked
    hass.states.async_set("light.test2", STATE_OFF, {ATTR_SUPPORTED_FEATURES: 256})
    await hass.async_block_till_done()
    state = hass.states.get("light.light_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 40


@pytest.mark.parametrize("supported_color_modes", [ColorMode.HS, ColorMode.RGB])
async def test_service_calls(
    hass: HomeAssistant, enable_custom_integrations: None, supported_color_modes
) -> None:
    """Test service calls."""
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    platform.ENTITIES.append(platform.MockLight("bed_light", STATE_ON))
    platform.ENTITIES.append(platform.MockLight("ceiling_lights", STATE_OFF))
    platform.ENTITIES.append(platform.MockLight("kitchen_lights", STATE_OFF))

    entity0 = platform.ENTITIES[0]
    entity0.supported_color_modes = {supported_color_modes}
    entity0.color_mode = supported_color_modes
    entity0.brightness = 255
    entity0.rgb_color = (0, 64, 128)

    entity1 = platform.ENTITIES[1]
    entity1.supported_color_modes = {supported_color_modes}
    entity1.color_mode = supported_color_modes
    entity1.brightness = 255
    entity1.rgb_color = (255, 128, 64)

    entity2 = platform.ENTITIES[2]
    entity2.supported_color_modes = {supported_color_modes}
    entity2.color_mode = supported_color_modes
    entity2.brightness = 255
    entity2.rgb_color = (255, 128, 64)

    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": DOMAIN,
                    "entities": [
                        "light.bed_light",
                        "light.ceiling_lights",
                        "light.kitchen_lights",
                    ],
                    "all": "false",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    group_state = hass.states.get("light.light_group")
    assert group_state.state == STATE_ON
    assert group_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [supported_color_modes]

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
            ATTR_RGB_COLOR: (42, 255, 255),
        },
        blocking=True,
    )

    state = hass.states.get("light.bed_light")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_RGB_COLOR] == (42, 255, 255)

    state = hass.states.get("light.ceiling_lights")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_RGB_COLOR] == (42, 255, 255)

    state = hass.states.get("light.kitchen_lights")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_RGB_COLOR] == (42, 255, 255)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.light_group",
            ATTR_BRIGHTNESS: 128,
            ATTR_COLOR_NAME: "red",
        },
        blocking=True,
    )

    state = hass.states.get("light.bed_light")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_RGB_COLOR] == (255, 0, 0)

    state = hass.states.get("light.ceiling_lights")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_RGB_COLOR] == (255, 0, 0)

    state = hass.states.get("light.kitchen_lights")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_RGB_COLOR] == (255, 0, 0)


async def test_service_call_effect(hass: HomeAssistant) -> None:
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
                    "all": "false",
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


async def test_invalid_service_calls(hass: HomeAssistant) -> None:
    """Test invalid service call arguments get discarded."""
    add_entities = MagicMock()
    await group.async_setup_platform(
        hass, {"name": "test", "entities": ["light.test1", "light.test2"]}, add_entities
    )
    await async_setup_component(hass, "light", {})
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert add_entities.call_count == 1
    grouped_light = add_entities.call_args[0][0][0]
    grouped_light.hass = hass

    service_call_events = async_capture_events(hass, EVENT_CALL_SERVICE)

    await grouped_light.async_turn_on(brightness=150, four_oh_four="404")
    data = {ATTR_ENTITY_ID: ["light.test1", "light.test2"], ATTR_BRIGHTNESS: 150}
    assert len(service_call_events) == 1
    service_event_call: Event = service_call_events[0]
    assert service_event_call.data["domain"] == LIGHT_DOMAIN
    assert service_event_call.data["service"] == SERVICE_TURN_ON
    assert service_event_call.data["service_data"] == data
    service_call_events.clear()

    await grouped_light.async_turn_off(transition=4, four_oh_four="404")
    data = {ATTR_ENTITY_ID: ["light.test1", "light.test2"], ATTR_TRANSITION: 4}
    assert len(service_call_events) == 1
    service_event_call: Event = service_call_events[0]
    assert service_event_call.data["domain"] == LIGHT_DOMAIN
    assert service_event_call.data["service"] == SERVICE_TURN_OFF
    assert service_event_call.data["service_data"] == data
    service_call_events.clear()

    data = {
        ATTR_BRIGHTNESS: 150,
        ATTR_COLOR_TEMP_KELVIN: 1234,
        ATTR_TRANSITION: 4,
    }
    await grouped_light.async_turn_on(**data)
    data[ATTR_ENTITY_ID] = ["light.test1", "light.test2"]
    service_event_call: Event = service_call_events[0]
    assert service_event_call.data["domain"] == LIGHT_DOMAIN
    assert service_event_call.data["service"] == SERVICE_TURN_ON
    assert service_event_call.data["service_data"] == data
    service_call_events.clear()


async def test_reload(hass: HomeAssistant) -> None:
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
                    "all": "false",
                },
            ]
        },
    )
    await hass.async_block_till_done()

    await hass.async_block_till_done()
    await hass.async_start()

    await hass.async_block_till_done()
    assert hass.states.get("light.light_group").state == STATE_ON

    yaml_path = get_fixture_path("configuration.yaml", "group")
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


async def test_reload_with_platform_not_setup(hass: HomeAssistant) -> None:
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

    yaml_path = get_fixture_path("configuration.yaml", "group")
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


async def test_reload_with_base_integration_platform_not_setup(
    hass: HomeAssistant,
) -> None:
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

    yaml_path = get_fixture_path("configuration.yaml", "group")
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


async def test_nested_group(hass: HomeAssistant) -> None:
    """Test nested light group."""
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": ["light.bedroom_group"],
                    "name": "Nested Group",
                    "all": "false",
                },
                {
                    "platform": DOMAIN,
                    "entities": ["light.bed_light", "light.kitchen_lights"],
                    "name": "Bedroom Group",
                    "all": "false",
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
    assert state.attributes.get(ATTR_ENTITY_ID) == [
        "light.bed_light",
        "light.kitchen_lights",
    ]

    state = hass.states.get("light.nested_group")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ENTITY_ID) == ["light.bedroom_group"]

    # Test controlling the nested group
    async with asyncio.timeout(0.5):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TOGGLE,
            {ATTR_ENTITY_ID: "light.nested_group"},
            blocking=True,
        )
    assert hass.states.get("light.bed_light").state == STATE_OFF
    assert hass.states.get("light.kitchen_lights").state == STATE_OFF
    assert hass.states.get("light.bedroom_group").state == STATE_OFF
    assert hass.states.get("light.nested_group").state == STATE_OFF
