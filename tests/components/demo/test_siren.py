"""The tests for the demo siren component."""
from unittest.mock import call, patch

import pytest

from homeassistant.components.siren import (
    ATTR_AVAILABLE_TONES,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ENTITY_SIREN = "siren.siren"
ENTITY_SIREN_WITH_ALL_FEATURES = "siren.siren_with_all_features"


@pytest.fixture(autouse=True)
async def setup_demo_siren(hass, disable_platforms):
    """Initialize setup demo siren."""
    assert await async_setup_component(hass, DOMAIN, {"siren": {"platform": "demo"}})
    await hass.async_block_till_done()


def test_setup_params(hass: HomeAssistant) -> None:
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_ON
    assert ATTR_AVAILABLE_TONES not in state.attributes


def test_all_setup_params(hass: HomeAssistant) -> None:
    """Test the setup with all parameters."""
    state = hass.states.get(ENTITY_SIREN_WITH_ALL_FEATURES)
    assert state.attributes.get(ATTR_AVAILABLE_TONES) == ["fire", "alarm"]


async def test_turn_on(hass: HomeAssistant) -> None:
    """Test turn on device."""
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_SIREN}, blocking=True
    )
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_SIREN}, blocking=True
    )
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_ON

    # Test that an invalid tone will raise a ValueError
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_SIREN_WITH_ALL_FEATURES, ATTR_TONE: "invalid_tone"},
            blocking=True,
        )


async def test_turn_off(hass: HomeAssistant) -> None:
    """Test turn off device."""
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_SIREN}, blocking=True
    )
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_ON

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_SIREN}, blocking=True
    )
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_OFF


async def test_toggle(hass: HomeAssistant) -> None:
    """Test toggle device."""
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_SIREN}, blocking=True
    )
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_ON

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_SIREN}, blocking=True
    )
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_SIREN}, blocking=True
    )
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_ON


async def test_turn_on_strip_attributes(hass: HomeAssistant) -> None:
    """Test attributes are stripped from turn_on service call when not supported."""
    with patch(
        "homeassistant.components.demo.siren.DemoSiren.async_turn_on"
    ) as svc_call:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_SIREN, ATTR_VOLUME_LEVEL: 1},
            blocking=True,
        )
        assert svc_call.called
        assert svc_call.call_args_list[0] == call()
