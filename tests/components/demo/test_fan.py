"""Test cases around the demo fan platform."""
import pytest

from homeassistant.components import fan
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from tests.components.fan import common

FAN_ENTITY_ID = "fan.living_room_fan"


def get_entity(hass):
    """Get the fan entity."""
    return hass.states.get(FAN_ENTITY_ID)


@pytest.fixture(autouse=True)
async def setup_comp(hass):
    """Initialize components."""
    assert await async_setup_component(hass, fan.DOMAIN, {"fan": {"platform": "demo"}})
    await hass.async_block_till_done()


async def test_turn_on(hass):
    """Test turning on the device."""
    assert STATE_OFF == get_entity(hass).state

    await common.async_turn_on(hass, FAN_ENTITY_ID)
    assert STATE_OFF != get_entity(hass).state

    await common.async_turn_on(hass, FAN_ENTITY_ID, fan.SPEED_HIGH)
    assert STATE_ON == get_entity(hass).state
    assert fan.SPEED_HIGH == get_entity(hass).attributes[fan.ATTR_SPEED]


async def test_turn_off(hass):
    """Test turning off the device."""
    assert STATE_OFF == get_entity(hass).state

    await common.async_turn_on(hass, FAN_ENTITY_ID)
    assert STATE_OFF != get_entity(hass).state

    await common.async_turn_off(hass, FAN_ENTITY_ID)
    assert STATE_OFF == get_entity(hass).state


async def test_turn_off_without_entity_id(hass):
    """Test turning off all fans."""
    assert STATE_OFF == get_entity(hass).state

    await common.async_turn_on(hass, FAN_ENTITY_ID)
    assert STATE_OFF != get_entity(hass).state

    await common.async_turn_off(hass)
    assert STATE_OFF == get_entity(hass).state


async def test_set_direction(hass):
    """Test setting the direction of the device."""
    assert STATE_OFF == get_entity(hass).state

    await common.async_set_direction(hass, FAN_ENTITY_ID, fan.DIRECTION_REVERSE)
    assert fan.DIRECTION_REVERSE == get_entity(hass).attributes.get("direction")


async def test_set_speed(hass):
    """Test setting the speed of the device."""
    assert STATE_OFF == get_entity(hass).state

    await common.async_set_speed(hass, FAN_ENTITY_ID, fan.SPEED_LOW)
    assert fan.SPEED_LOW == get_entity(hass).attributes.get("speed")


async def test_oscillate(hass):
    """Test oscillating the fan."""
    assert not get_entity(hass).attributes.get("oscillating")

    await common.async_oscillate(hass, FAN_ENTITY_ID, True)
    assert get_entity(hass).attributes.get("oscillating")

    await common.async_oscillate(hass, FAN_ENTITY_ID, False)
    assert not get_entity(hass).attributes.get("oscillating")


async def test_is_on(hass):
    """Test is on service call."""
    assert not fan.is_on(hass, FAN_ENTITY_ID)

    await common.async_turn_on(hass, FAN_ENTITY_ID)
    assert fan.is_on(hass, FAN_ENTITY_ID)
