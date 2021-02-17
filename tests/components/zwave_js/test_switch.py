"""Test the Z-Wave JS switch platform."""

from zwave_js_server.event import Event

from homeassistant.components.switch import DOMAIN, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.const import STATE_OFF, STATE_ON

from .common import SWITCH_ENTITY


async def test_switch(hass, hank_binary_switch, integration, client):
    """Test the switch."""
    state = hass.states.get(SWITCH_ENTITY)
    node = hank_binary_switch

    assert state
    assert state.state == "off"

    # Test turning on
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": SWITCH_ENTITY}, blocking=True
    )

    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 32
    assert args["valueId"] == {
        "commandClassName": "Binary Switch",
        "commandClass": 37,
        "endpoint": 0,
        "property": "targetValue",
        "propertyName": "targetValue",
        "metadata": {
            "type": "boolean",
            "readable": True,
            "writeable": True,
            "label": "Target value",
        },
        "value": False,
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

    # Test turning off
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": SWITCH_ENTITY}, blocking=True
    )

    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 32
    assert args["valueId"] == {
        "commandClassName": "Binary Switch",
        "commandClass": 37,
        "endpoint": 0,
        "property": "targetValue",
        "propertyName": "targetValue",
        "metadata": {
            "type": "boolean",
            "readable": True,
            "writeable": True,
            "label": "Target value",
        },
        "value": False,
    }
    assert args["value"] is False


async def test_barrier_signaling_switch(hass, gdc_zw062, integration, client):
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
        "ccVersion": 0,
        "commandClass": 102,
        "commandClassName": "Barrier Operator",
        "endpoint": 0,
        "metadata": {
            "label": "Signaling State (Visual)",
            "max": 255,
            "min": 0,
            "readable": True,
            "states": {"0": "Off", "255": "On"},
            "type": "number",
            "writeable": True,
        },
        "property": "signalingState",
        "propertyKey": 2,
        "propertyKeyName": "2",
        "propertyName": "signalingState",
        "value": 255,
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
        "ccVersion": 0,
        "commandClass": 102,
        "commandClassName": "Barrier Operator",
        "endpoint": 0,
        "metadata": {
            "label": "Signaling State (Visual)",
            "max": 255,
            "min": 0,
            "readable": True,
            "states": {"0": "Off", "255": "On"},
            "type": "number",
            "writeable": True,
        },
        "property": "signalingState",
        "propertyKey": 2,
        "propertyKeyName": "2",
        "propertyName": "signalingState",
        "value": 255,
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
