"""Test the Z-Wave JS cover platform."""
from zwave_js_server.const import (
    CURRENT_STATE_PROPERTY,
    CURRENT_VALUE_PROPERTY,
    CommandClass,
)
from zwave_js_server.event import Event
from zwave_js_server.model.node import Node

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    CoverDeviceClass,
)
from homeassistant.components.zwave_js.helpers import ZwaveValueMatcher
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from .common import replace_value_of_zwave_value

WINDOW_COVER_ENTITY = "cover.zws_12"
GDC_COVER_ENTITY = "cover.aeon_labs_garage_door_controller_gen5"
BLIND_COVER_ENTITY = "cover.window_blind_controller"
SHUTTER_COVER_ENTITY = "cover.flush_shutter"
AEOTEC_SHUTTER_COVER_ENTITY = "cover.nano_shutter_v_3"
FIBARO_SHUTTER_COVER_ENTITY = "cover.fgr_222_test_cover"


async def test_window_cover(
    hass: HomeAssistant, client, chain_actuator_zws12, integration
) -> None:
    """Test the cover entity."""
    node = chain_actuator_zws12
    state = hass.states.get(WINDOW_COVER_ENTITY)

    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.WINDOW

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
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
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
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
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
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
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

    assert len(client.async_send_command.call_args_list) == 1
    open_args = client.async_send_command.call_args_list[0][0][0]
    assert open_args["command"] == "node.set_value"
    assert open_args["nodeId"] == 6
    assert open_args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "Open",
    }
    assert not open_args["value"]

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
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
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

    assert len(client.async_send_command.call_args_list) == 1
    open_args = client.async_send_command.call_args_list[0][0][0]
    assert open_args["command"] == "node.set_value"
    assert open_args["nodeId"] == 6
    assert open_args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "Open",
    }
    assert not open_args["value"]

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


async def test_fibaro_FGR222_shutter_cover(
    hass: HomeAssistant, client, fibaro_fgr222_shutter, integration
) -> None:
    """Test tilt function of the Fibaro Shutter devices."""
    state = hass.states.get(FIBARO_SHUTTER_COVER_ENTITY)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.SHUTTER

    assert state.state == "open"
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0

    # Test opening tilts
    await hass.services.async_call(
        "cover",
        "open_cover_tilt",
        {"entity_id": FIBARO_SHUTTER_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 42
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 145,
        "property": "fibaro",
        "propertyKey": "venetianBlindsTilt",
    }
    assert args["value"] == 99

    client.async_send_command.reset_mock()
    # Test closing tilts
    await hass.services.async_call(
        "cover",
        "close_cover_tilt",
        {"entity_id": FIBARO_SHUTTER_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 42
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 145,
        "property": "fibaro",
        "propertyKey": "venetianBlindsTilt",
    }
    assert args["value"] == 0

    # Test some tilt
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 42,
            "args": {
                "commandClassName": "Manufacturer Proprietary",
                "commandClass": 145,
                "endpoint": 0,
                "property": "fibaro",
                "propertyKey": "venetianBlindsTilt",
                "newValue": 99,
                "prevValue": 0,
                "propertyName": "fibaro",
                "propertyKeyName": "venetianBlindsTilt",
            },
        },
    )
    fibaro_fgr222_shutter.receive_event(event)
    state = hass.states.get(FIBARO_SHUTTER_COVER_ENTITY)
    assert state
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100


async def test_aeotec_nano_shutter_cover(
    hass: HomeAssistant, client, aeotec_nano_shutter, integration
) -> None:
    """Test movement of an Aeotec Nano Shutter cover entity. Useful to make sure the stop command logic is handled properly."""
    node = aeotec_nano_shutter
    state = hass.states.get(AEOTEC_SHUTTER_COVER_ENTITY)

    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.WINDOW

    assert state.state == "closed"
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    # Test opening
    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": AEOTEC_SHUTTER_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 3
    assert args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"]

    client.async_send_command.reset_mock()
    # Test stop after opening
    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": AEOTEC_SHUTTER_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    open_args = client.async_send_command.call_args_list[0][0][0]
    assert open_args["command"] == "node.set_value"
    assert open_args["nodeId"] == 3
    assert open_args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "On",
    }
    assert not open_args["value"]

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

    state = hass.states.get(AEOTEC_SHUTTER_COVER_ENTITY)
    assert state.state == "open"

    # Test closing
    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": AEOTEC_SHUTTER_COVER_ENTITY},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 3
    assert args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"] == 0

    client.async_send_command.reset_mock()

    # Test stop after closing
    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": AEOTEC_SHUTTER_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    open_args = client.async_send_command.call_args_list[0][0][0]
    assert open_args["command"] == "node.set_value"
    assert open_args["nodeId"] == 3
    assert open_args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "On",
    }
    assert not open_args["value"]


async def test_blind_cover(
    hass: HomeAssistant, client, iblinds_v2, integration
) -> None:
    """Test a blind cover entity."""
    state = hass.states.get(BLIND_COVER_ENTITY)

    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.BLIND


async def test_shutter_cover(
    hass: HomeAssistant, client, qubino_shutter, integration
) -> None:
    """Test a shutter cover entity."""
    state = hass.states.get(SHUTTER_COVER_ENTITY)

    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.SHUTTER


async def test_motor_barrier_cover(
    hass: HomeAssistant, client, gdc_zw062, integration
) -> None:
    """Test the cover entity."""
    node = gdc_zw062

    state = hass.states.get(GDC_COVER_ENTITY)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.GARAGE

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
        "commandClass": 102,
        "endpoint": 0,
        "property": "targetState",
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
        "commandClass": 102,
        "endpoint": 0,
        "property": "targetState",
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


async def test_motor_barrier_cover_no_primary_value(
    hass: HomeAssistant, client, gdc_zw062_state, integration
) -> None:
    """Test the cover entity where primary value value is None."""
    node_state = replace_value_of_zwave_value(
        gdc_zw062_state,
        [
            ZwaveValueMatcher(
                property_=CURRENT_STATE_PROPERTY,
                command_class=CommandClass.BARRIER_OPERATOR,
            )
        ],
        None,
    )
    node = Node(client, node_state)
    client.driver.controller.emit("node added", {"node": node})
    await hass.async_block_till_done()

    state = hass.states.get(GDC_COVER_ENTITY)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.GARAGE

    assert state.state == STATE_UNKNOWN
    assert ATTR_CURRENT_POSITION not in state.attributes


async def test_fibaro_FGR222_shutter_cover_no_tilt(
    hass: HomeAssistant, client, fibaro_fgr222_shutter_state, integration
) -> None:
    """Test tilt function of the Fibaro Shutter devices with tilt value is None."""
    node_state = replace_value_of_zwave_value(
        fibaro_fgr222_shutter_state,
        [
            ZwaveValueMatcher(
                property_="fibaro",
                command_class=CommandClass.MANUFACTURER_PROPRIETARY,
                property_key="venetianBlindsTilt",
            ),
            ZwaveValueMatcher(
                property_=CURRENT_VALUE_PROPERTY,
                command_class=CommandClass.SWITCH_MULTILEVEL,
            ),
        ],
        None,
    )
    node = Node(client, node_state)
    client.driver.controller.emit("node added", {"node": node})
    await hass.async_block_till_done()

    state = hass.states.get(FIBARO_SHUTTER_COVER_ENTITY)
    assert state
    assert state.state == STATE_UNKNOWN
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes
