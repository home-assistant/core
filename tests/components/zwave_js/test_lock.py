"""Test the Z-Wave JS lock platform."""
from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.lock import (
    ATTR_CODE_SLOT,
    ATTR_USERCODE,
    CURRENT_MODE_PROPERTY,
)
from zwave_js_server.event import Event
from zwave_js_server.model.node import Node, NodeStatus

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.components.zwave_js.const import DOMAIN as ZWAVE_JS_DOMAIN
from homeassistant.components.zwave_js.helpers import ZwaveValueMatcher
from homeassistant.components.zwave_js.lock import (
    SERVICE_CLEAR_LOCK_USERCODE,
    SERVICE_SET_LOCK_USERCODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_LOCKED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    STATE_UNLOCKED,
)
from homeassistant.core import HomeAssistant

from .common import SCHLAGE_BE469_LOCK_ENTITY, replace_value_of_zwave_value


async def test_door_lock(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test a lock entity with door lock command class."""
    node = lock_schlage_be469
    state = hass.states.get(SCHLAGE_BE469_LOCK_ENTITY)

    assert state
    assert state.state == STATE_UNLOCKED

    # Test locking
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 20
    assert args["valueId"] == {
        "commandClass": 98,
        "endpoint": 0,
        "property": "targetMode",
    }
    assert args["value"] == 255

    client.async_send_command.reset_mock()

    # Test locked update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 20,
            "args": {
                "commandClassName": "Door Lock",
                "commandClass": 98,
                "endpoint": 0,
                "property": "currentMode",
                "newValue": 255,
                "prevValue": 0,
                "propertyName": "currentMode",
            },
        },
    )
    node.receive_event(event)

    assert hass.states.get(SCHLAGE_BE469_LOCK_ENTITY).state == STATE_LOCKED

    client.async_send_command.reset_mock()

    # Test unlocking
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 20
    assert args["valueId"] == {
        "commandClass": 98,
        "endpoint": 0,
        "property": "targetMode",
    }
    assert args["value"] == 0

    client.async_send_command.reset_mock()

    # Test set usercode service
    await hass.services.async_call(
        ZWAVE_JS_DOMAIN,
        SERVICE_SET_LOCK_USERCODE,
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
            ATTR_CODE_SLOT: 1,
            ATTR_USERCODE: "1234",
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 20
    assert args["valueId"] == {
        "commandClass": 99,
        "endpoint": 0,
        "property": "userCode",
        "propertyKey": 1,
    }
    assert args["value"] == "1234"

    client.async_send_command.reset_mock()

    # Test clear usercode
    await hass.services.async_call(
        ZWAVE_JS_DOMAIN,
        SERVICE_CLEAR_LOCK_USERCODE,
        {ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY, ATTR_CODE_SLOT: 1},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 20
    assert args["valueId"] == {
        "commandClass": 99,
        "endpoint": 0,
        "property": "userIdStatus",
        "propertyKey": 1,
    }
    assert args["value"] == 0

    event = Event(
        type="dead",
        data={
            "source": "node",
            "event": "dead",
            "nodeId": 20,
        },
    )
    node.receive_event(event)

    assert node.status == NodeStatus.DEAD
    assert hass.states.get(SCHLAGE_BE469_LOCK_ENTITY).state == STATE_UNAVAILABLE


async def test_only_one_lock(
    hass: HomeAssistant, client, lock_home_connect_620, integration
) -> None:
    """Test node with both Door Lock and Lock CC values only gets one lock entity."""
    assert len(hass.states.async_entity_ids("lock")) == 1


async def test_door_lock_no_value(
    hass: HomeAssistant, client, lock_schlage_be469_state, integration
) -> None:
    """Test a lock entity with door lock command class that has no value for mode."""
    node_state = replace_value_of_zwave_value(
        lock_schlage_be469_state,
        [
            ZwaveValueMatcher(
                property_=CURRENT_MODE_PROPERTY,
                command_class=CommandClass.DOOR_LOCK,
            )
        ],
        None,
    )
    node = Node(client, node_state)
    client.driver.controller.emit("node added", {"node": node})
    await hass.async_block_till_done()
    state = hass.states.get(SCHLAGE_BE469_LOCK_ENTITY)
    assert state
    assert state.state == STATE_UNKNOWN
