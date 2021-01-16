"""Test the Z-Wave JS lock platform."""
from zwave_js_server.event import Event

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_LOCKED, STATE_UNLOCKED

SCHLAGE_BE469_LOCK_ENTITY = "lock.touchscreen_deadbolt_current_lock_mode"


async def test_door_lock(hass, client, lock_schlage_be469, integration):
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
        "commandClassName": "Door Lock",
        "commandClass": 98,
        "endpoint": 0,
        "property": "targetMode",
        "propertyName": "targetMode",
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "min": 0,
            "max": 255,
            "label": "Target lock mode",
            "states": {
                "0": "Unsecured",
                "1": "UnsecuredWithTimeout",
                "16": "InsideUnsecured",
                "17": "InsideUnsecuredWithTimeout",
                "32": "OutsideUnsecured",
                "33": "OutsideUnsecuredWithTimeout",
                "254": "Unknown",
                "255": "Secured",
            },
        },
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
        "commandClassName": "Door Lock",
        "commandClass": 98,
        "endpoint": 0,
        "property": "targetMode",
        "propertyName": "targetMode",
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "min": 0,
            "max": 255,
            "label": "Target lock mode",
            "states": {
                "0": "Unsecured",
                "1": "UnsecuredWithTimeout",
                "16": "InsideUnsecured",
                "17": "InsideUnsecuredWithTimeout",
                "32": "OutsideUnsecured",
                "33": "OutsideUnsecuredWithTimeout",
                "254": "Unknown",
                "255": "Secured",
            },
        },
    }
    assert args["value"] == 0
