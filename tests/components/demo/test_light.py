"""The tests for the demo light component."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.demo import DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_XY_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    LightService,
    LightServiceArgument,
)
from homeassistant.const import STATE_OFF, STATE_ON, Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ENTITY_LIGHT = "light.bed_light"


@pytest.fixture
def light_only() -> Generator[None]:
    """Enable only the light platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.LIGHT],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_comp(hass: HomeAssistant, light_only: None) -> None:
    """Set up demo component."""
    assert await async_setup_component(
        hass, LIGHT_DOMAIN, {LIGHT_DOMAIN: {"platform": DOMAIN}}
    )
    await hass.async_block_till_done()


async def test_state_attributes(hass: HomeAssistant) -> None:
    """Test light state attributes."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {
            TargetKey.ENTITY_ID: ENTITY_LIGHT,
            LightServiceArgument.XY_COLOR: (0.4, 0.4),
            LightServiceArgument.BRIGHTNESS: 25,
        },
        blocking=True,
    )

    state = hass.states.get(ENTITY_LIGHT)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_XY_COLOR) == (0.4, 0.4)
    assert state.attributes.get(ATTR_BRIGHTNESS) == 25
    assert state.attributes.get(ATTR_RGB_COLOR) == (255, 234, 164)
    assert state.attributes.get(ATTR_EFFECT) == "rainbow"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {
            TargetKey.ENTITY_ID: ENTITY_LIGHT,
            LightServiceArgument.RGB_COLOR: (251, 253, 255),
        },
        blocking=True,
    )

    state = hass.states.get(ENTITY_LIGHT)
    assert state.attributes.get(ATTR_RGB_COLOR) == (251, 253, 255)
    assert state.attributes.get(ATTR_XY_COLOR) == (0.319, 0.327)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {
            TargetKey.ENTITY_ID: ENTITY_LIGHT,
            LightServiceArgument.EFFECT: "off",
            LightServiceArgument.COLOR_TEMP_KELVIN: 2500,
        },
        blocking=True,
    )

    state = hass.states.get(ENTITY_LIGHT)
    assert state.attributes.get(ATTR_COLOR_TEMP_KELVIN) == 2500
    assert state.attributes.get(ATTR_MAX_COLOR_TEMP_KELVIN) == 6535
    assert state.attributes.get(ATTR_MIN_COLOR_TEMP_KELVIN) == 2000
    assert state.attributes.get(ATTR_EFFECT) == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {
            TargetKey.ENTITY_ID: ENTITY_LIGHT,
            LightServiceArgument.BRIGHTNESS_PCT: 50,
            LightServiceArgument.COLOR_TEMP_KELVIN: 3000,
        },
        blocking=True,
    )

    state = hass.states.get(ENTITY_LIGHT)
    assert state.attributes.get(ATTR_COLOR_TEMP_KELVIN) == 3000
    assert state.attributes.get(ATTR_BRIGHTNESS) == 128


async def test_turn_off(hass: HomeAssistant) -> None:
    """Test light turn off method."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: ENTITY_LIGHT},
        blocking=True,
    )

    state = hass.states.get(ENTITY_LIGHT)
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: ENTITY_LIGHT},
        blocking=True,
    )

    state = hass.states.get(ENTITY_LIGHT)
    assert state.state == STATE_OFF


async def test_turn_off_without_entity_id(hass: HomeAssistant) -> None:
    """Test light turn off all lights."""
    await hass.services.async_call(
        LIGHT_DOMAIN, LightService.TURN_ON, {TargetKey.ENTITY_ID: "all"}, blocking=True
    )

    state = hass.states.get(ENTITY_LIGHT)
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN, LightService.TURN_OFF, {TargetKey.ENTITY_ID: "all"}, blocking=True
    )

    state = hass.states.get(ENTITY_LIGHT)
    assert state.state == STATE_OFF
