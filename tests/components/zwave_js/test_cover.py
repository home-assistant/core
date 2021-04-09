"""Test the Z-Wave JS cover platform."""
from zwave_js_server.event import Event

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    DEVICE_CLASS_GARAGE,
    DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNKNOWN,
)

WINDOW_COVER_ENTITY = "cover.zws_12"
GDC_COVER_ENTITY = "cover.aeon_labs_garage_door_controller_gen5"


async def test_window_cover(hass, client, chain_actuator_zws12, integration):
    """Test the cover entity."""
    node = chain_actuator_zws12
    state = hass.states.get(WINDOW_COVER_ENTITY)

    assert state
    assert state.state == "closed"
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    # Test setting position
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": WINDOW_COVER_ENTITY, "position": 50},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 6
    assert args["valueId"] == {
        "commandClassName": "Multilevel Switch",
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
        "propertyName": "targetValue",
        "metadata": {
            "label": "Target value",
            "max": 99,
            "min": 0,
            "type": "number",
            "readable": True,
            "writeable": True,
            "label": "Target value",
        },
    }
    assert args["value"] == 50

    client.async_send_command.reset_mock()

    # Test setting position
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": WINDOW_COVER_ENTITY, "position": 0},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 6
    assert args["valueId"] == {
        "commandClassName": "Multilevel Switch",
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
        "propertyName": "targetValue",
        "metadata": {
            "label": "Target value",
            "max": 99,
            "min": 0,
            "type": "number",
            "readable": True,
            "writeable": True,
            "label": "Target value",
        },
    }
    assert args["value"] == 0

    client.async_send_command.reset_mock()

    # Test opening
    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": WINDOW_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 6
    assert args["valueId"] == {
        "commandClassName": "Multilevel Switch",
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
        "propertyName": "targetValue",
        "metadata": {
            "label": "Target value",
            "max": 99,
            "min": 0,
            "type": "number",
            "readable": True,
            "writeable": True,
            "label": "Target value",
        },
    }
    assert args["value"]

    client.async_send_command.reset_mock()
    # Test stop after opening
    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": WINDOW_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    open_args = client.async_send_command.call_args_list[0][0][0]
    assert open_args["command"] == "node.set_value"
    assert open_args["nodeId"] == 6
    assert open_args["valueId"] == {
        "commandClassName": "Multilevel Switch",
        "commandClass": 38,
        "endpoint": 0,
        "property": "Open",
        "propertyName": "Open",
        "metadata": {
            "type": "boolean",
            "readable": True,
            "writeable": True,
            "label": "Perform a level change (Open)",
            "ccSpecific": {"switchType": 3},
        },
    }
    assert not open_args["value"]

    close_args = client.async_send_command.call_args_list[1][0][0]
    assert close_args["command"] == "node.set_value"
    assert close_args["nodeId"] == 6
    assert close_args["valueId"] == {
        "commandClassName": "Multilevel Switch",
        "commandClass": 38,
        "endpoint": 0,
        "property": "Close",
        "propertyName": "Close",
        "metadata": {
            "type": "boolean",
            "readable": True,
            "writeable": True,
            "label": "Perform a level change (Close)",
            "ccSpecific": {"switchType": 3},
        },
    }
    assert not close_args["value"]

    # Test position update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 6,
            "args": {
                "commandClassName": "Multilevel Switch",
                "commandClass": 38,
                "endpoint": 0,
                "property": "currentValue",
                "newValue": 99,
                "prevValue": 0,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)
    client.async_send_command.reset_mock()

    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state.state == "open"

    # Test closing
    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": WINDOW_COVER_ENTITY},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 6
    assert args["valueId"] == {
        "commandClassName": "Multilevel Switch",
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
        "propertyName": "targetValue",
        "metadata": {
            "label": "Target value",
            "max": 99,
            "min": 0,
            "type": "number",
            "readable": True,
            "writeable": True,
            "label": "Target value",
        },
    }
    assert args["value"] == 0

    client.async_send_command.reset_mock()

    # Test stop after closing
    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": WINDOW_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    open_args = client.async_send_command.call_args_list[0][0][0]
    assert open_args["command"] == "node.set_value"
    assert open_args["nodeId"] == 6
    assert open_args["valueId"] == {
        "commandClassName": "Multilevel Switch",
        "commandClass": 38,
        "endpoint": 0,
        "property": "Open",
        "propertyName": "Open",
        "metadata": {
            "type": "boolean",
            "readable": True,
            "writeable": True,
            "label": "Perform a level change (Open)",
            "ccSpecific": {"switchType": 3},
        },
    }
    assert not open_args["value"]

    close_args = client.async_send_command.call_args_list[1][0][0]
    assert close_args["command"] == "node.set_value"
    assert close_args["nodeId"] == 6
    assert close_args["valueId"] == {
        "commandClassName": "Multilevel Switch",
        "commandClass": 38,
        "endpoint": 0,
        "property": "Close",
        "propertyName": "Close",
        "metadata": {
            "type": "boolean",
            "readable": True,
            "writeable": True,
            "label": "Perform a level change (Close)",
            "ccSpecific": {"switchType": 3},
        },
    }
    assert not close_args["value"]

    client.async_send_command.reset_mock()

    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 6,
            "args": {
                "commandClassName": "Multilevel Switch",
                "commandClass": 38,
                "endpoint": 0,
                "property": "currentValue",
                "newValue": 0,
                "prevValue": 0,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state.state == "closed"


async def test_motor_barrier_cover(hass, client, gdc_zw062, integration):
    """Test the cover entity."""
    node = gdc_zw062

    state = hass.states.get(GDC_COVER_ENTITY)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_GARAGE

    assert state.state == STATE_CLOSED

    # Test open
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER, {"entity_id": GDC_COVER_ENTITY}, blocking=True
    )

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
            "label": "Target Barrier State",
            "max": 255,
            "min": 0,
            "readable": True,
            "states": {"0": "Closed", "255": "Open"},
            "type": "number",
            "writeable": True,
        },
        "property": "targetState",
        "propertyName": "targetState",
    }

    # state doesn't change until currentState value update is received
    state = hass.states.get(GDC_COVER_ENTITY)
    assert state.state == STATE_CLOSED

    client.async_send_command.reset_mock()

    # Test close
    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER, {"entity_id": GDC_COVER_ENTITY}, blocking=True
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
            "label": "Target Barrier State",
            "max": 255,
            "min": 0,
            "readable": True,
            "states": {"0": "Closed", "255": "Open"},
            "type": "number",
            "writeable": True,
        },
        "property": "targetState",
        "propertyName": "targetState",
    }

    # state doesn't change until currentState value update is received
    state = hass.states.get(GDC_COVER_ENTITY)
    assert state.state == STATE_CLOSED

    client.async_send_command.reset_mock()

    # Barrier sends an opening state
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
                "property": "currentState",
                "newValue": 254,
                "prevValue": 0,
                "propertyName": "currentState",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(GDC_COVER_ENTITY)
    assert state.state == STATE_OPENING

    # Barrier sends an opened state
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
                "property": "currentState",
                "newValue": 255,
                "prevValue": 254,
                "propertyName": "currentState",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(GDC_COVER_ENTITY)
    assert state.state == STATE_OPEN

    # Barrier sends a closing state
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
                "property": "currentState",
                "newValue": 252,
                "prevValue": 255,
                "propertyName": "currentState",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(GDC_COVER_ENTITY)
    assert state.state == STATE_CLOSING

    # Barrier sends a closed state
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
                "property": "currentState",
                "newValue": 0,
                "prevValue": 252,
                "propertyName": "currentState",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(GDC_COVER_ENTITY)
    assert state.state == STATE_CLOSED

    # Barrier sends a stopped state
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
                "property": "currentState",
                "newValue": 253,
                "prevValue": 252,
                "propertyName": "currentState",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(GDC_COVER_ENTITY)
    assert state.state == STATE_UNKNOWN
