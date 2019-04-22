"""Test cases around the demo fan platform."""
import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components import fan
from homeassistant.const import STATE_OFF, STATE_ON

from tests.components.fan import common

FAN_ENTITY_ID = 'fan.living_room_fan'


def get_entity(hass):
    """Get the fan entity."""
    return hass.states.get(FAN_ENTITY_ID)


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    hass.loop.run_until_complete(async_setup_component(hass, fan.DOMAIN, {
        'fan': {
            'platform': 'demo',
        }
    }))


async def test_turn_on(hass):
    """Test turning on the device."""
    assert STATE_OFF == get_entity(hass).state

    common.async_turn_on(hass, FAN_ENTITY_ID)
    await hass.async_block_till_done()
    assert STATE_OFF != get_entity(hass).state

    common.async_turn_on(hass, FAN_ENTITY_ID, fan.SPEED_HIGH)
    await hass.async_block_till_done()
    assert STATE_ON == get_entity(hass).state
    assert fan.SPEED_HIGH == \
        get_entity(hass).attributes[fan.ATTR_SPEED]


async def test_turn_off(hass):
    """Test turning off the device."""
    assert STATE_OFF == get_entity(hass).state

    common.async_turn_on(hass, FAN_ENTITY_ID)
    await hass.async_block_till_done()
    assert STATE_OFF != get_entity(hass).state

    common.async_turn_off(hass, FAN_ENTITY_ID)
    await hass.async_block_till_done()
    assert STATE_OFF == get_entity(hass).state


async def test_turn_off_without_entity_id(hass):
    """Test turning off all fans."""
    assert STATE_OFF == get_entity(hass).state

    common.async_turn_on(hass, FAN_ENTITY_ID)
    await hass.async_block_till_done()
    assert STATE_OFF != get_entity(hass).state

    common.async_turn_off(hass)
    await hass.async_block_till_done()
    assert STATE_OFF == get_entity(hass).state


async def test_set_direction(hass):
    """Test setting the direction of the device."""
    assert STATE_OFF == get_entity(hass).state

    common.async_set_direction(hass, FAN_ENTITY_ID, fan.DIRECTION_REVERSE)
    await hass.async_block_till_done()
    assert fan.DIRECTION_REVERSE == \
        get_entity(hass).attributes.get('direction')


async def test_set_speed(hass):
    """Test setting the speed of the device."""
    assert STATE_OFF == get_entity(hass).state

    common.async_set_speed(hass, FAN_ENTITY_ID, fan.SPEED_LOW)
    await hass.async_block_till_done()
    assert fan.SPEED_LOW == \
        get_entity(hass).attributes.get('speed')


async def test_oscillate(hass):
    """Test oscillating the fan."""
    assert not get_entity(hass).attributes.get('oscillating')

    common.async_oscillate(hass, FAN_ENTITY_ID, True)
    await hass.async_block_till_done()
    assert get_entity(hass).attributes.get('oscillating')

    common.async_oscillate(hass, FAN_ENTITY_ID, False)
    await hass.async_block_till_done()
    assert not get_entity(hass).attributes.get('oscillating')


async def test_is_on(hass):
    """Test is on service call."""
    assert not fan.is_on(hass, FAN_ENTITY_ID)

    common.async_turn_on(hass, FAN_ENTITY_ID)
    await hass.async_block_till_done()
    assert fan.is_on(hass, FAN_ENTITY_ID)
