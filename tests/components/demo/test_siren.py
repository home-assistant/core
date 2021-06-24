"""The tests for the demo siren component."""

import pytest
import voluptuous as vol

from homeassistant.components.siren import is_on
from homeassistant.components.siren.const import (
    ATTR_AVAILABLE_TONES,
    ATTR_DEFAULT_DURATION,
    ATTR_DEFAULT_TONE,
    ATTR_DURATION,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    DOMAIN,
    SERVICE_SET_DEFAULT_DURATION,
    SERVICE_SET_DEFAULT_TONE,
    SERVICE_SET_VOLUME_LEVEL,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.setup import async_setup_component

ENTITY_SIREN = "siren.siren"
ENTITY_SIREN_WITH_ALL_FEATURES = "siren.siren_with_all_features"


@pytest.fixture(autouse=True)
async def setup_demo_siren(hass):
    """Initialize setup demo siren."""
    assert await async_setup_component(hass, DOMAIN, {"siren": {"platform": "demo"}})
    await hass.async_block_till_done()


def test_setup_params(hass):
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_ON
    assert ATTR_VOLUME_LEVEL not in state.attributes
    assert ATTR_DEFAULT_TONE not in state.attributes
    assert ATTR_AVAILABLE_TONES not in state.attributes
    assert ATTR_DEFAULT_DURATION not in state.attributes


def test_all_setup_params(hass):
    """Test the setup with all parameters."""
    state = hass.states.get(ENTITY_SIREN_WITH_ALL_FEATURES)
    assert state.attributes.get(ATTR_DEFAULT_TONE) == "fire"
    assert state.attributes.get(ATTR_AVAILABLE_TONES) == ["fire", "alarm"]
    assert state.attributes.get(ATTR_VOLUME_LEVEL) == 0.5
    assert state.attributes.get(ATTR_DEFAULT_DURATION) == 5


async def test_set_volume_level_bad_attr(hass):
    """Test setting the volume level without required attribute."""
    state = hass.states.get(ENTITY_SIREN_WITH_ALL_FEATURES)
    assert state.attributes.get(ATTR_VOLUME_LEVEL) == 0.5

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VOLUME_LEVEL,
            {ATTR_VOLUME_LEVEL: None, ATTR_ENTITY_ID: ENTITY_SIREN_WITH_ALL_FEATURES},
            blocking=True,
        )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_SIREN_WITH_ALL_FEATURES)
    assert state.attributes.get(ATTR_VOLUME_LEVEL) == 0.5


async def test_set_volume_level(hass):
    """Test the setting of the volume level."""
    state = hass.states.get(ENTITY_SIREN_WITH_ALL_FEATURES)
    assert state.attributes.get(ATTR_VOLUME_LEVEL) == 0.5

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VOLUME_LEVEL,
        {ATTR_VOLUME_LEVEL: 0.75, ATTR_ENTITY_ID: ENTITY_SIREN_WITH_ALL_FEATURES},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_SIREN_WITH_ALL_FEATURES)
    assert state.attributes.get(ATTR_VOLUME_LEVEL) == 0.75


async def test_set_default_tone_bad_attr(hass):
    """Test setting the default tone without required attribute."""
    state = hass.states.get(ENTITY_SIREN_WITH_ALL_FEATURES)
    assert state.attributes.get(ATTR_DEFAULT_TONE) == "fire"

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DEFAULT_TONE,
            {ATTR_TONE: None, ATTR_ENTITY_ID: ENTITY_SIREN_WITH_ALL_FEATURES},
            blocking=True,
        )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_SIREN_WITH_ALL_FEATURES)
    assert state.attributes.get(ATTR_DEFAULT_TONE) == "fire"


async def test_set_default_tone(hass):
    """Test the setting of the default tone."""
    state = hass.states.get(ENTITY_SIREN_WITH_ALL_FEATURES)
    assert state.attributes.get(ATTR_DEFAULT_TONE) == "fire"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DEFAULT_TONE,
        {ATTR_TONE: "alarm", ATTR_ENTITY_ID: ENTITY_SIREN_WITH_ALL_FEATURES},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_SIREN_WITH_ALL_FEATURES)
    assert state.attributes.get(ATTR_DEFAULT_TONE) == "alarm"


async def test_set_default_duration_bad_attr(hass):
    """Test setting the default duration without required attribute."""
    state = hass.states.get(ENTITY_SIREN_WITH_ALL_FEATURES)
    assert state.attributes.get(ATTR_DEFAULT_DURATION) == 5

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DEFAULT_DURATION,
            {ATTR_DURATION: None, ATTR_ENTITY_ID: ENTITY_SIREN_WITH_ALL_FEATURES},
            blocking=True,
        )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_SIREN_WITH_ALL_FEATURES)
    assert state.attributes.get(ATTR_DEFAULT_DURATION) == 5


async def test_set_default_duration(hass):
    """Test the setting of the default duration."""
    state = hass.states.get(ENTITY_SIREN_WITH_ALL_FEATURES)
    assert state.attributes.get(ATTR_DEFAULT_DURATION) == 5

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DEFAULT_DURATION,
        {ATTR_DURATION: 10, ATTR_ENTITY_ID: ENTITY_SIREN_WITH_ALL_FEATURES},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_SIREN_WITH_ALL_FEATURES)
    assert state.attributes.get(ATTR_DEFAULT_DURATION) == 10


async def test_turn_on(hass):
    """Test turn on device."""
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_SIREN}, blocking=True
    )
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_OFF
    assert not is_on(hass, ENTITY_SIREN)

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_SIREN}, blocking=True
    )
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_ON
    assert is_on(hass, ENTITY_SIREN)


async def test_turn_off(hass):
    """Test turn off device."""
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_SIREN}, blocking=True
    )
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_ON
    assert is_on(hass, ENTITY_SIREN)

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_SIREN}, blocking=True
    )
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_OFF
    assert not is_on(hass, ENTITY_SIREN)


async def test_toggle(hass):
    """Test toggle device."""
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_SIREN}, blocking=True
    )
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_ON
    assert is_on(hass, ENTITY_SIREN)

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_SIREN}, blocking=True
    )
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_OFF
    assert not is_on(hass, ENTITY_SIREN)

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_SIREN}, blocking=True
    )
    state = hass.states.get(ENTITY_SIREN)
    assert state.state == STATE_ON
    assert is_on(hass, ENTITY_SIREN)
