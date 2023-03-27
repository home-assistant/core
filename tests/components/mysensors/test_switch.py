"""Provide tests for mysensors switch platform."""
from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock, call

from mysensors.sensor import Sensor

from homeassistant.components.mysensors.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant


async def test_relay_node(
    hass: HomeAssistant,
    relay_node: Sensor,
    receive_message: Callable[[str], None],
    transport_write: MagicMock,
) -> None:
    """Test a relay node."""
    entity_id = "switch.relay_node_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;2;1\n")

    receive_message("1;1;1;0;2;1\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "on"

    transport_write.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;2;0\n")

    receive_message("1;1;1;0;2;0\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "off"


async def test_ir_transceiver(
    hass: HomeAssistant,
    ir_transceiver: Sensor,
    receive_message: Callable[[str], None],
    transport_write: MagicMock,
) -> None:
    """Test an ir transceiver."""
    entity_id = "switch.ir_transceiver_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 2
    assert transport_write.call_args_list[0] == call("1;1;1;0;32;test_code\n")
    assert transport_write.call_args_list[1] == call("1;1;1;1;2;1\n")

    receive_message("1;1;1;0;2;1\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "on"
    assert state.attributes["V_IR_SEND"] == "test_code"

    transport_write.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;2;0\n")

    receive_message("1;1;1;0;2;0\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "off"

    transport_write.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        "send_ir_code",
        {"entity_id": entity_id, "V_IR_SEND": "new_code"},
        blocking=True,
    )

    assert transport_write.call_count == 2
    assert transport_write.call_args_list[0] == call("1;1;1;0;32;new_code\n")
    assert transport_write.call_args_list[1] == call("1;1;1;1;2;1\n")

    receive_message("1;1;1;0;32;new_code\n")
    receive_message("1;1;1;0;2;1\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "on"
    assert state.attributes["V_IR_SEND"] == "new_code"
