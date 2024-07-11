"""Test the Z-Wave JS lock platform."""

import pytest
from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.lock import (
    ATTR_CODE_SLOT,
    ATTR_USERCODE,
    CURRENT_MODE_PROPERTY,
)
from zwave_js_server.event import Event
from zwave_js_server.exceptions import FailedZWaveCommand
from zwave_js_server.model.node import Node, NodeStatus

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.components.zwave_js.const import (
    ATTR_LOCK_TIMEOUT,
    ATTR_OPERATION_TYPE,
    DOMAIN as ZWAVE_JS_DOMAIN,
)
from homeassistant.components.zwave_js.helpers import ZwaveValueMatcher
from homeassistant.components.zwave_js.lock import (
    SERVICE_CLEAR_LOCK_USERCODE,
    SERVICE_SET_LOCK_CONFIGURATION,
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
from homeassistant.exceptions import HomeAssistantError

from .common import SCHLAGE_BE469_LOCK_ENTITY, replace_value_of_zwave_value


async def test_door_lock(
    hass: HomeAssistant,
    client,
    lock_schlage_be469,
    integration,
    caplog: pytest.LogCaptureFixture,
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

    client.async_send_command.reset_mock()

    # Test set configuration
    client.async_send_command.return_value = {
        "response": {"status": 1, "remainingDuration": "default"}
    }
    caplog.clear()
    await hass.services.async_call(
        ZWAVE_JS_DOMAIN,
        SERVICE_SET_LOCK_CONFIGURATION,
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
            ATTR_OPERATION_TYPE: "timed",
            ATTR_LOCK_TIMEOUT: 1,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "endpoint.invoke_cc_api"
    assert args["nodeId"] == 20
    assert args["endpoint"] == 0
    assert args["args"] == [
        {
            "insideHandlesCanOpenDoorConfiguration": [True, True, True, True],
            "operationType": 2,
            "outsideHandlesCanOpenDoorConfiguration": [True, True, True, True],
        }
    ]
    assert args["commandClass"] == 98
    assert args["methodName"] == "setConfiguration"
    assert "Result status" in caplog.text
    assert "remaining duration" in caplog.text
    assert "setting lock configuration" in caplog.text

    client.async_send_command.reset_mock()
    client.async_send_command_no_wait.reset_mock()
    caplog.clear()

    # Put node to sleep and validate that we don't wait for a return or log anything
    event = Event(
        "sleep",
        {
            "source": "node",
            "event": "sleep",
            "nodeId": node.node_id,
        },
    )
    node.receive_event(event)

    await hass.services.async_call(
        ZWAVE_JS_DOMAIN,
        SERVICE_SET_LOCK_CONFIGURATION,
        {
            ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY,
            ATTR_OPERATION_TYPE: "timed",
            ATTR_LOCK_TIMEOUT: 1,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 0
    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "endpoint.invoke_cc_api"
    assert args["nodeId"] == 20
    assert args["endpoint"] == 0
    assert args["args"] == [
        {
            "insideHandlesCanOpenDoorConfiguration": [True, True, True, True],
            "operationType": 2,
            "outsideHandlesCanOpenDoorConfiguration": [True, True, True, True],
        }
    ]
    assert args["commandClass"] == 98
    assert args["methodName"] == "setConfiguration"
    assert "Result status" not in caplog.text
    assert "remaining duration" not in caplog.text
    assert "setting lock configuration" not in caplog.text

    # Mark node as alive
    event = Event(
        "alive",
        {
            "source": "node",
            "event": "alive",
            "nodeId": node.node_id,
        },
    )
    node.receive_event(event)

    client.async_send_command.side_effect = FailedZWaveCommand("test", 1, "test")
    # Test set usercode service error handling
    with pytest.raises(HomeAssistantError):
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

    # Test clear usercode service error handling
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            ZWAVE_JS_DOMAIN,
            SERVICE_CLEAR_LOCK_USERCODE,
            {ATTR_ENTITY_ID: SCHLAGE_BE469_LOCK_ENTITY, ATTR_CODE_SLOT: 1},
            blocking=True,
        )

    client.async_send_command.reset_mock()

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
