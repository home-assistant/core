"""The tests for the demo number component."""

import pytest
import voluptuous as vol

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_SET_VALUE,
    NumberMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ENTITY_VOLUME = "number.volume"
ENTITY_PWM = "number.pwm_1"
ENTITY_LARGE_RANGE = "number.large_range"
ENTITY_SMALL_RANGE = "number.small_range"


@pytest.fixture(autouse=True)
async def setup_demo_number(hass):
    """Initialize setup demo Number entity."""
    assert await async_setup_component(hass, DOMAIN, {"number": {"platform": "demo"}})
    await hass.async_block_till_done()


def test_setup_params(hass: HomeAssistant) -> None:
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_VOLUME)
    assert state.state == "42.0"


def test_default_setup_params(hass: HomeAssistant) -> None:
    """Test the setup with default parameters."""
    state = hass.states.get(ENTITY_VOLUME)
    assert state.attributes.get(ATTR_MIN) == 0.0
    assert state.attributes.get(ATTR_MAX) == 100.0
    assert state.attributes.get(ATTR_STEP) == 1.0
    assert state.attributes.get(ATTR_MODE) == NumberMode.SLIDER

    state = hass.states.get(ENTITY_PWM)
    assert state.attributes.get(ATTR_MIN) == 0.0
    assert state.attributes.get(ATTR_MAX) == 1.0
    assert state.attributes.get(ATTR_STEP) == 0.01
    assert state.attributes.get(ATTR_MODE) == NumberMode.BOX

    state = hass.states.get(ENTITY_LARGE_RANGE)
    assert state.attributes.get(ATTR_MIN) == 1.0
    assert state.attributes.get(ATTR_MAX) == 1000.0
    assert state.attributes.get(ATTR_STEP) == 1.0
    assert state.attributes.get(ATTR_MODE) == NumberMode.AUTO

    state = hass.states.get(ENTITY_SMALL_RANGE)
    assert state.attributes.get(ATTR_MIN) == 1.0
    assert state.attributes.get(ATTR_MAX) == 255.0
    assert state.attributes.get(ATTR_STEP) == 1.0
    assert state.attributes.get(ATTR_MODE) == NumberMode.AUTO


async def test_set_value_bad_attr(hass: HomeAssistant) -> None:
    """Test setting the value without required attribute."""
    state = hass.states.get(ENTITY_VOLUME)
    assert state.state == "42.0"

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: None, ATTR_ENTITY_ID: ENTITY_VOLUME},
            blocking=True,
        )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_VOLUME)
    assert state.state == "42.0"


async def test_set_value_bad_range(hass: HomeAssistant) -> None:
    """Test setting the value out of range."""
    state = hass.states.get(ENTITY_VOLUME)
    assert state.state == "42.0"

    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: 1024, ATTR_ENTITY_ID: ENTITY_VOLUME},
            blocking=True,
        )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_VOLUME)
    assert state.state == "42.0"


async def test_set_set_value(hass: HomeAssistant) -> None:
    """Test the setting of the value."""
    state = hass.states.get(ENTITY_VOLUME)
    assert state.state == "42.0"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 23, ATTR_ENTITY_ID: ENTITY_VOLUME},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_VOLUME)
    assert state.state == "23.0"
