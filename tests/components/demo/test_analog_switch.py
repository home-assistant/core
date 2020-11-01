"""The tests for the demo analog switch component."""

import pytest
import voluptuous as vol

from homeassistant.components.analog_switch.const import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_DECREMENT,
    SERVICE_INCREMENT,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.setup import async_setup_component

ENTITY_VOLUME = "analog_switch.volume"


@pytest.fixture(autouse=True)
async def setup_demo_analog_switch(hass):
    """Initialize setup demo analog switch."""
    assert await async_setup_component(
        hass, DOMAIN, {"analog_switch": {"platform": "demo"}}
    )
    await hass.async_block_till_done()


def test_setup_params(hass):
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_VOLUME)
    assert state.state == "42.0"


def test_default_setup_params(hass):
    """Test the setup with default parameters."""
    state = hass.states.get(ENTITY_VOLUME)
    assert state.attributes.get(ATTR_MIN) == 0.0
    assert state.attributes.get(ATTR_MAX) == 100.0
    assert state.attributes.get(ATTR_STEP) == 1.0


async def test_set_value_bad_attr(hass):
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


async def test_set_set_value(hass):
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


async def test_increment(hass):
    """Test setting the hold mode away."""
    state = hass.states.get(ENTITY_VOLUME)
    assert state.state == "42.0"

    await hass.services.async_call(
        DOMAIN, SERVICE_INCREMENT, {ATTR_ENTITY_ID: ENTITY_VOLUME}, blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_VOLUME)
    assert state.state == "43.0"


async def test_decrement(hass):
    """Test setting the hold mode away."""
    state = hass.states.get(ENTITY_VOLUME)
    assert state.state == "42.0"

    await hass.services.async_call(
        DOMAIN, SERVICE_DECREMENT, {ATTR_ENTITY_ID: ENTITY_VOLUME}, blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_VOLUME)
    assert state.state == "41.0"
