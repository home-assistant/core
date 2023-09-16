"""Test the Z-Wave JS switch platform."""
import pytest
from zwave_js_server.const import CURRENT_VALUE_PROPERTY, CommandClass
from zwave_js_server.event import Event
from zwave_js_server.exceptions import FailedZWaveCommand
from zwave_js_server.model.node import Node

from homeassistant.components.switch import DOMAIN, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.components.zwave_js.helpers import ZwaveValueMatcher
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import SWITCH_ENTITY, replace_value_of_zwave_value


async def test_switch(
    hass: HomeAssistant, hank_binary_switch, integration, client
) -> None:
    """Test the switch."""
    state = hass.states.get(SWITCH_ENTITY)
    node = hank_binary_switch

    assert state
    assert state.state == STATE_OFF

    # Test turning on
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": SWITCH_ENTITY}, blocking=True
    )

    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 32
    assert args["valueId"] == {
        "commandClass": 37,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"] is True

    # Test state updates from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 32,
            "args": {
                "commandClassName": "Binary Switch",
                "commandClass": 37,
                "endpoint": 0,
                "property": "currentValue",
                "newValue": True,
                "prevValue": False,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(SWITCH_ENTITY)
    assert state.state == "on"

    client.async_send_command.reset_mock()

    # Test turning off
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": SWITCH_ENTITY}, blocking=True
    )

    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 32
    assert args["valueId"] == {
        "commandClass": 37,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"] is False


async def test_barrier_signaling_switch(
    hass: HomeAssistant, gdc_zw062, integration, client
) -> None:
    """Test barrier signaling state switch."""
    node = gdc_zw062
    entity = "switch.aeon_labs_garage_door_controller_gen5_signaling_state_visual"

    state = hass.states.get(entity)
    assert state
    assert state.state == "on"

    # Test turning off
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {"entity_id": entity}, blocking=True
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 12
    assert args["value"] == 0
    assert args["valueId"] == {
        "commandClass": 102,
        "endpoint": 0,
        "property": "signalingState",
        "propertyKey": 2,
    }

    # state change is optimistic and writes state
    await hass.async_block_till_done()

    state = hass.states.get(entity)
    assert state.state == STATE_OFF

    client.async_send_command.reset_mock()

    # Test turning on
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {"entity_id": entity}, blocking=True
    )

    # Note: the valueId's value is still 255 because we never
    # received an updated value
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 12
    assert args["value"] == 255
    assert args["valueId"] == {
        "commandClass": 102,
        "endpoint": 0,
        "property": "signalingState",
        "propertyKey": 2,
    }

    # state change is optimistic and writes state
    await hass.async_block_till_done()

    state = hass.states.get(entity)
    assert state.state == STATE_ON

    # Received a refresh off
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 12,
            "args": {
                "commandClassName": "Barrier Operator",
                "commandClass": 102,
                "endpoint": 0,
                "property": "signalingState",
                "propertyKey": 2,
                "newValue": 0,
                "prevValue": 0,
                "propertyName": "signalingState",
                "propertyKeyName": "2",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(entity)
    assert state.state == STATE_OFF

    # Received a refresh off
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 12,
            "args": {
                "commandClassName": "Barrier Operator",
                "commandClass": 102,
                "endpoint": 0,
                "property": "signalingState",
                "propertyKey": 2,
                "newValue": 255,
                "prevValue": 255,
                "propertyName": "signalingState",
                "propertyKeyName": "2",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(entity)
    assert state.state == STATE_ON


async def test_switch_no_value(
    hass: HomeAssistant, hank_binary_switch_state, integration, client
) -> None:
    """Test the switch where primary value value is None."""
    node_state = replace_value_of_zwave_value(
        hank_binary_switch_state,
        [
            ZwaveValueMatcher(
                property_=CURRENT_VALUE_PROPERTY,
                command_class=CommandClass.SWITCH_BINARY,
            )
        ],
        None,
    )
    node = Node(client, node_state)
    client.driver.controller.emit("node added", {"node": node})
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_ENTITY)

    assert state
    assert state.state == STATE_UNKNOWN


async def test_config_parameter_switch(
    hass: HomeAssistant, hank_binary_switch, integration, client
) -> None:
    """Test config parameter switch is created."""
    switch_entity_id = "switch.smart_plug_with_two_usb_ports_overload_protection"
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(switch_entity_id)
    assert entity_entry
    assert entity_entry.disabled

    updated_entry = ent_reg.async_update_entity(
        switch_entity_id, **{"disabled_by": None}
    )
    assert updated_entry != entity_entry
    assert updated_entry.disabled is False
    assert entity_entry.entity_category == EntityCategory.CONFIG

    # reload integration and check if entity is correctly there
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(switch_entity_id)
    assert state
    assert state.state == STATE_ON

    client.async_send_command.reset_mock()

    # Test turning on
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {"entity_id": switch_entity_id}, blocking=True
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == hank_binary_switch.node_id
    assert args["value"] == 1
    assert args["valueId"] == {
        "commandClass": 112,
        "endpoint": 0,
        "property": 20,
    }

    client.async_send_command.reset_mock()

    # Test turning off
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {"entity_id": switch_entity_id}, blocking=True
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == hank_binary_switch.node_id
    assert args["value"] == 0
    assert args["valueId"] == {
        "commandClass": 112,
        "endpoint": 0,
        "property": 20,
    }

    client.async_send_command.reset_mock()
    client.async_send_command.side_effect = FailedZWaveCommand("test", 1, "test")

    # Test turning off error raises proper exception
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, SERVICE_TURN_OFF, {"entity_id": switch_entity_id}, blocking=True
        )
