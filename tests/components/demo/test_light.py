"""The tests for the demo light component."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.demo import DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_KELVIN,
    ATTR_MAX_MIREDS,
    ATTR_MIN_MIREDS,
    ATTR_RGB_COLOR,
    ATTR_XY_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
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
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_XY_COLOR: (0.4, 0.4), ATTR_BRIGHTNESS: 25},
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
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
            ATTR_RGB_COLOR: (251, 253, 255),
        },
        blocking=True,
    )

    state = hass.states.get(ENTITY_LIGHT)
    assert state.attributes.get(ATTR_RGB_COLOR) == (250, 252, 255)
    assert state.attributes.get(ATTR_XY_COLOR) == (0.319, 0.326)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_EFFECT: "none", ATTR_COLOR_TEMP: 400},
        blocking=True,
    )

    state = hass.states.get(ENTITY_LIGHT)
    assert state.attributes.get(ATTR_COLOR_TEMP) == 400
    assert state.attributes.get(ATTR_MIN_MIREDS) == 153
    assert state.attributes.get(ATTR_MAX_MIREDS) == 500
    assert state.attributes.get(ATTR_EFFECT) == "none"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_BRIGHTNESS_PCT: 50, ATTR_KELVIN: 3000},
        blocking=True,
    )

    state = hass.states.get(ENTITY_LIGHT)
    assert state.attributes.get(ATTR_COLOR_TEMP) == 333
    assert state.attributes.get(ATTR_BRIGHTNESS) == 128


async def test_turn_off(hass: HomeAssistant) -> None:
    """Test light turn off method."""
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_LIGHT}, blocking=True
    )

    state = hass.states.get(ENTITY_LIGHT)
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_LIGHT}, blocking=True
    )

    state = hass.states.get(ENTITY_LIGHT)
    assert state.state == STATE_OFF


async def test_turn_off_without_entity_id(hass: HomeAssistant) -> None:
    """Test light turn off all lights."""
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: "all"}, blocking=True
    )

    state = hass.states.get(ENTITY_LIGHT)
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "all"}, blocking=True
    )

    state = hass.states.get(ENTITY_LIGHT)
    assert state.state == STATE_OFF
