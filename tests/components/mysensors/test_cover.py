"""Provide tests for mysensors cover platform."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock, call

from mysensors.sensor import Sensor

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    CoverState,
)
from homeassistant.const import ATTR_BATTERY_LEVEL, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


async def test_cover_node_percentage(
    hass: HomeAssistant,
    cover_node_percentage: Sensor,
    receive_message: Callable[[str], None],
    transport_write: MagicMock,
) -> None:
    """Test a cover percentage node."""
    entity_id = "cover.cover_node_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0
    assert state.attributes[ATTR_BATTERY_LEVEL] == 0

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;29;1\n")

    receive_message("1;1;1;0;29;1\n")
    receive_message("1;1;1;0;3;50\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == CoverState.OPENING
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    transport_write.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;31;1\n")

    receive_message("1;1;1;0;31;1\n")
    receive_message("1;1;1;0;3;50\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    transport_write.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;29;1\n")

    receive_message("1;1;1;0;31;0\n")
    receive_message("1;1;1;0;29;1\n")
    receive_message("1;1;1;0;3;75\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == CoverState.OPENING
    assert state.attributes[ATTR_CURRENT_POSITION] == 75

    receive_message("1;1;1;0;29;0\n")
    receive_message("1;1;1;0;3;100\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100

    transport_write.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;30;1\n")

    receive_message("1;1;1;0;30;1\n")
    receive_message("1;1;1;0;3;50\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == CoverState.CLOSING
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    receive_message("1;1;1;0;30;0\n")
    receive_message("1;1;1;0;3;0\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    transport_write.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 25},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;3;25\n")

    receive_message("1;1;1;0;3;25\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 25


async def test_cover_node_binary(
    hass: HomeAssistant,
    cover_node_binary: Sensor,
    receive_message: Callable[[str], None],
    transport_write: MagicMock,
) -> None:
    """Test a cover binary node."""
    entity_id = "cover.cover_node_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == CoverState.CLOSED

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;29;1\n")

    receive_message("1;1;1;0;29;1\n")
    receive_message("1;1;1;0;2;1\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == CoverState.OPENING

    transport_write.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;31;1\n")

    receive_message("1;1;1;0;31;1\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == CoverState.OPEN

    transport_write.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;29;1\n")

    receive_message("1;1;1;0;31;0\n")
    receive_message("1;1;1;0;29;1\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == CoverState.OPENING

    receive_message("1;1;1;0;29;0\n")
    receive_message("1;1;1;0;2;1\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == CoverState.OPEN

    transport_write.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;30;1\n")

    receive_message("1;1;1;0;30;1\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == CoverState.CLOSING

    receive_message("1;1;1;0;30;0\n")
    receive_message("1;1;1;0;2;0\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == CoverState.CLOSED
