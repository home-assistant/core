"""Test cases around the demo fan platform."""
import pytest

from homeassistant.components import fan
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.setup import async_setup_component

FAN_ENTITY_ID = "fan.living_room_fan"


@pytest.fixture(autouse=True)
async def setup_comp(hass):
    """Initialize components."""
    assert await async_setup_component(hass, fan.DOMAIN, {"fan": {"platform": "demo"}})
    await hass.async_block_till_done()


async def test_turn_on(hass):
    """Test turning on the device."""
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        fan.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: FAN_ENTITY_ID}, blocking=True
    )
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.state == STATE_ON

    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, fan.ATTR_SPEED: fan.SPEED_HIGH},
        blocking=True,
    )
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_SPEED] == fan.SPEED_HIGH


async def test_turn_off(hass):
    """Test turning off the device."""
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        fan.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: FAN_ENTITY_ID}, blocking=True
    )
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.state == STATE_ON

    await hass.services.async_call(
        fan.DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: FAN_ENTITY_ID}, blocking=True
    )
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.state == STATE_OFF


async def test_turn_off_without_entity_id(hass):
    """Test turning off all fans."""
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        fan.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: FAN_ENTITY_ID}, blocking=True
    )
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.state == STATE_ON

    await hass.services.async_call(
        fan.DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_MATCH_ALL}, blocking=True
    )
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.state == STATE_OFF


async def test_set_direction(hass):
    """Test setting the direction of the device."""
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_SET_DIRECTION,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, fan.ATTR_DIRECTION: fan.DIRECTION_REVERSE},
        blocking=True,
    )
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.attributes[fan.ATTR_DIRECTION] == fan.DIRECTION_REVERSE


async def test_set_speed(hass):
    """Test setting the speed of the device."""
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_SET_SPEED,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, fan.ATTR_SPEED: fan.SPEED_LOW},
        blocking=True,
    )
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.attributes[fan.ATTR_SPEED] == fan.SPEED_LOW


async def test_oscillate(hass):
    """Test oscillating the fan."""
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.state == STATE_OFF
    assert not state.attributes.get(fan.ATTR_OSCILLATING)

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_OSCILLATE,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, fan.ATTR_OSCILLATING: True},
        blocking=True,
    )
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.attributes[fan.ATTR_OSCILLATING] is True

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_OSCILLATE,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, fan.ATTR_OSCILLATING: False},
        blocking=True,
    )
    state = hass.states.get(FAN_ENTITY_ID)
    assert state.attributes[fan.ATTR_OSCILLATING] is False


async def test_is_on(hass):
    """Test is on service call."""
    assert not fan.is_on(hass, FAN_ENTITY_ID)

    await hass.services.async_call(
        fan.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: FAN_ENTITY_ID}, blocking=True
    )
    assert fan.is_on(hass, FAN_ENTITY_ID)
