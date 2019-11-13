"""The tests for the demo humidifier component."""

import pytest
import voluptuous as vol

from homeassistant.components.humidifier.const import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HUMIDIFIER_ACTIONS,
    ATTR_HUMIDIFIER_MODE,
    ATTR_HUMIDIFIER_MODES,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    ATTR_PRESET_MODE,
    CURRENT_HUMIDIFIER_DRY,
    DOMAIN,
    HUMIDIFIER_MODE_DRY,
    HUMIDIFIER_MODE_HUMIDIFY,
    HUMIDIFIER_MODE_OFF,
    PRESET_AWAY,
    PRESET_ECO,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HUMIDIFIER_MODE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.setup import async_setup_component

ENTITY_DEHUMIDIFIER = "humidifier.dehumidifier"
ENTITY_HYGROSTAT = "humidifier.hygrostat"
ENTITY_HUMIDIFIER = "humidifier.humidifier"


@pytest.fixture(autouse=True)
async def setup_demo_humidifier(hass):
    """Initialize setup demo humidifier."""
    assert await async_setup_component(
        hass, DOMAIN, {"humidifier": {"platform": "demo"}}
    )


def test_setup_params(hass):
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.state == HUMIDIFIER_MODE_DRY
    assert "On High" == state.attributes.get(ATTR_FAN_MODE)
    assert 54 == state.attributes.get(ATTR_HUMIDITY)
    assert 67 == state.attributes.get(ATTR_CURRENT_HUMIDITY)
    assert state.attributes.get(ATTR_HUMIDIFIER_MODES) == ["dry", "off"]


def test_default_setup_params(hass):
    """Test the setup with default parameters."""
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert 30 == state.attributes.get(ATTR_MIN_HUMIDITY)
    assert 99 == state.attributes.get(ATTR_MAX_HUMIDITY)


async def test_set_target_humidity_bad_attr(hass):
    """Test setting the target humidity without required attribute."""
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert 54 == state.attributes.get(ATTR_HUMIDITY)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HUMIDITY,
            {ATTR_HUMIDITY: None, ATTR_ENTITY_ID: ENTITY_DEHUMIDIFIER},
            blocking=True,
        )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert 54 == state.attributes.get(ATTR_HUMIDITY)


async def test_set_target_humidity(hass):
    """Test the setting of the target humidity."""
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert 54 == state.attributes.get(ATTR_HUMIDITY)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_HUMIDITY: 64, ATTR_ENTITY_ID: ENTITY_DEHUMIDIFIER},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert 64.0 == state.attributes.get(ATTR_HUMIDITY)


async def test_set_fan_mode_bad_attr(hass):
    """Test setting fan mode without required attribute."""
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert "On High" == state.attributes.get(ATTR_FAN_MODE)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: None, ATTR_ENTITY_ID: ENTITY_DEHUMIDIFIER},
            blocking=True,
        )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert "On High" == state.attributes.get(ATTR_FAN_MODE)


async def test_set_fan_mode(hass):
    """Test setting of new fan mode."""
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert "On High" == state.attributes.get(ATTR_FAN_MODE)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_FAN_MODE: "On Low", ATTR_ENTITY_ID: ENTITY_DEHUMIDIFIER},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert "On Low" == state.attributes.get(ATTR_FAN_MODE)


async def test_set_humidifier_bad_attr_and_state(hass):
    """Test setting humidifier mode without required attribute.

    Also check the state.
    """
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.attributes.get(ATTR_HUMIDIFIER_ACTIONS) == CURRENT_HUMIDIFIER_DRY
    assert state.state == HUMIDIFIER_MODE_DRY

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HUMIDIFIER_MODE,
            {ATTR_HUMIDIFIER_MODE: None, ATTR_ENTITY_ID: ENTITY_DEHUMIDIFIER},
            blocking=True,
        )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.attributes.get(ATTR_HUMIDIFIER_ACTIONS) == CURRENT_HUMIDIFIER_DRY
    assert state.state == HUMIDIFIER_MODE_DRY


async def test_set_humidifier(hass):
    """Test setting of new humidifier mode."""
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.state == HUMIDIFIER_MODE_DRY

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HUMIDIFIER_MODE,
        {
            ATTR_HUMIDIFIER_MODE: HUMIDIFIER_MODE_HUMIDIFY,
            ATTR_ENTITY_ID: ENTITY_DEHUMIDIFIER,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.state == HUMIDIFIER_MODE_HUMIDIFY


async def test_set_hold_mode_away(hass):
    """Test setting the hold mode away."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_PRESET_MODE: PRESET_AWAY, ATTR_ENTITY_ID: ENTITY_HYGROSTAT},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_HYGROSTAT)
    assert state.attributes.get(ATTR_PRESET_MODE) == PRESET_AWAY


async def test_set_hold_mode_eco(hass):
    """Test setting the hold mode eco."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_PRESET_MODE: PRESET_ECO, ATTR_ENTITY_ID: ENTITY_HYGROSTAT},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_HYGROSTAT)
    assert state.attributes.get(ATTR_PRESET_MODE) == PRESET_ECO


async def test_turn_on(hass):
    """Test turn on device."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HUMIDIFIER_MODE,
        {
            ATTR_HUMIDIFIER_MODE: HUMIDIFIER_MODE_OFF,
            ATTR_ENTITY_ID: ENTITY_DEHUMIDIFIER,
        },
        blocking=True,
    )
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.state == HUMIDIFIER_MODE_OFF

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_DEHUMIDIFIER}, blocking=True
    )
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.state == HUMIDIFIER_MODE_DRY


async def test_turn_off(hass):
    """Test turn off device."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HUMIDIFIER_MODE,
        {
            ATTR_HUMIDIFIER_MODE: HUMIDIFIER_MODE_HUMIDIFY,
            ATTR_ENTITY_ID: ENTITY_DEHUMIDIFIER,
        },
        blocking=True,
    )
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.state == HUMIDIFIER_MODE_HUMIDIFY

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_DEHUMIDIFIER}, blocking=True
    )
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.state == HUMIDIFIER_MODE_OFF
