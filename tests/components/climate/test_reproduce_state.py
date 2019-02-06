"""The tests for reproduction of state."""

import pytest

from homeassistant.components.climate import STATE_HEAT, async_reproduce_states
from homeassistant.components.climate.const import (
    ATTR_AUX_HEAT, ATTR_AWAY_MODE, ATTR_HOLD_MODE, ATTR_HUMIDITY,
    ATTR_OPERATION_MODE, ATTR_SWING_MODE, ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW, DOMAIN, SERVICE_SET_AUX_HEAT, SERVICE_SET_AWAY_MODE,
    SERVICE_SET_HOLD_MODE, SERVICE_SET_HUMIDITY, SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_SWING_MODE, SERVICE_SET_TEMPERATURE)
from homeassistant.const import (
    ATTR_TEMPERATURE, SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF, STATE_ON)
from homeassistant.core import Context, State

from tests.common import async_mock_service

ENTITY_1 = 'climate.test1'
ENTITY_2 = 'climate.test2'


@pytest.mark.parametrize(
    'service,state', [
        (SERVICE_TURN_ON, STATE_ON),
        (SERVICE_TURN_OFF, STATE_OFF),
    ])
async def test_state(hass, service, state):
    """Test that we can turn a state into a service call."""
    calls_1 = async_mock_service(hass, DOMAIN, service)

    await async_reproduce_states(hass, [
        State(ENTITY_1, state)
    ])

    await hass.async_block_till_done()

    assert len(calls_1) == 1
    assert calls_1[0].data == {'entity_id': ENTITY_1}


async def test_turn_on_with_mode(hass):
    """Test that state with additional attributes call multiple services."""
    calls_1 = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    calls_2 = async_mock_service(hass, DOMAIN, SERVICE_SET_OPERATION_MODE)

    await async_reproduce_states(hass, [
        State(ENTITY_1, 'on',
              {ATTR_OPERATION_MODE: STATE_HEAT})
    ])

    await hass.async_block_till_done()

    assert len(calls_1) == 1
    assert calls_1[0].data == {'entity_id': ENTITY_1}

    assert len(calls_2) == 1
    assert calls_2[0].data == {'entity_id': ENTITY_1,
                               ATTR_OPERATION_MODE: STATE_HEAT}


async def test_multiple_same_state(hass):
    """Test that multiple states with same state gets calls."""
    calls_1 = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)

    await async_reproduce_states(hass, [
        State(ENTITY_1, 'on'),
        State(ENTITY_2, 'on'),
    ])

    await hass.async_block_till_done()

    assert len(calls_1) == 2
    # order is not guaranteed
    assert any(call.data == {'entity_id': ENTITY_1} for call in calls_1)
    assert any(call.data == {'entity_id': ENTITY_2} for call in calls_1)


async def test_multiple_different_state(hass):
    """Test that multiple states with different state gets calls."""
    calls_1 = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    calls_2 = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)

    await async_reproduce_states(hass, [
        State(ENTITY_1, 'on'),
        State(ENTITY_2, 'off'),
    ])

    await hass.async_block_till_done()

    assert len(calls_1) == 1
    assert calls_1[0].data == {'entity_id': ENTITY_1}
    assert len(calls_2) == 1
    assert calls_2[0].data == {'entity_id': ENTITY_2}


async def test_state_with_context(hass):
    """Test that context is forwarded."""
    calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)

    context = Context()

    await async_reproduce_states(hass, [
        State(ENTITY_1, 'on')
    ], context)

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {'entity_id': ENTITY_1}
    assert calls[0].context == context


async def test_attribute_no_state(hass):
    """Test that no state service call is made with none state."""
    calls_1 = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    calls_2 = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)
    calls_3 = async_mock_service(hass, DOMAIN, SERVICE_SET_OPERATION_MODE)

    value = "dummy"

    await async_reproduce_states(hass, [
        State(ENTITY_1, None,
              {ATTR_OPERATION_MODE: value})
    ])

    await hass.async_block_till_done()

    assert len(calls_1) == 0
    assert len(calls_2) == 0
    assert len(calls_3) == 1
    assert calls_3[0].data == {'entity_id': ENTITY_1,
                               ATTR_OPERATION_MODE: value}


@pytest.mark.parametrize(
    'service,attribute', [
        (SERVICE_SET_OPERATION_MODE, ATTR_OPERATION_MODE),
        (SERVICE_SET_AUX_HEAT, ATTR_AUX_HEAT),
        (SERVICE_SET_AWAY_MODE, ATTR_AWAY_MODE),
        (SERVICE_SET_HOLD_MODE, ATTR_HOLD_MODE),
        (SERVICE_SET_SWING_MODE, ATTR_SWING_MODE),
        (SERVICE_SET_HUMIDITY, ATTR_HUMIDITY),
        (SERVICE_SET_TEMPERATURE, ATTR_TEMPERATURE),
        (SERVICE_SET_TEMPERATURE, ATTR_TARGET_TEMP_HIGH),
        (SERVICE_SET_TEMPERATURE, ATTR_TARGET_TEMP_LOW),
    ])
async def test_attribute(hass, service, attribute):
    """Test that service call is made for each attribute."""
    calls_1 = async_mock_service(hass, DOMAIN, service)

    value = "dummy"

    await async_reproduce_states(hass, [
        State(ENTITY_1, None,
              {attribute: value})
    ])

    await hass.async_block_till_done()

    assert len(calls_1) == 1
    assert calls_1[0].data == {'entity_id': ENTITY_1,
                               attribute: value}
