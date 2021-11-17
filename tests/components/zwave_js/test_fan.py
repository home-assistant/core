"""Test the Z-Wave JS fan platform."""
import math

import pytest
from zwave_js_server.event import Event

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PERCENTAGE_STEP,
    ATTR_SPEED,
    SPEED_MEDIUM,
)

STANDARD_FAN_ENTITY = "fan.in_wall_smart_fan_control"
HS_FAN_ENTITY = "fan.scene_capable_fan_control_switch"


async def test_standard_fan(hass, client, in_wall_smart_fan_control, integration):
    """Test the fan entity."""
    node = in_wall_smart_fan_control
    state = hass.states.get(STANDARD_FAN_ENTITY)

    assert state
    assert state.state == "off"

    # Test turn on setting speed
    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": STANDARD_FAN_ENTITY, "speed": SPEED_MEDIUM},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 17
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
    assert args["value"] == 66

    client.async_send_command.reset_mock()

    # Test setting unknown speed
    with pytest.raises(ValueError):
        await hass.services.async_call(
            "fan",
            "set_speed",
            {"entity_id": STANDARD_FAN_ENTITY, "speed": 99},
            blocking=True,
        )

    client.async_send_command.reset_mock()

    # Test turn on no speed
    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": STANDARD_FAN_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 17
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
    assert args["value"] == 255

    client.async_send_command.reset_mock()

    # Test turning off
    await hass.services.async_call(
        "fan",
        "turn_off",
        {"entity_id": STANDARD_FAN_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 17
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

    # Test speed update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 17,
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

    state = hass.states.get(STANDARD_FAN_ENTITY)
    assert state.state == "on"
    assert state.attributes[ATTR_SPEED] == "high"

    client.async_send_command.reset_mock()

    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 17,
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

    state = hass.states.get(STANDARD_FAN_ENTITY)
    assert state.state == "off"
    assert state.attributes[ATTR_SPEED] == "off"


async def test_hs_fan(hass, client, hs_fc200, integration):
    """Test a fan entity with configurable speeds."""

    async def assert_percentage_to_zwave_speed(percentage, zwave_speed):
        """Assert that a percentage input is translated to a specific Zwave speed."""
        await hass.services.async_call(
            "fan",
            "turn_on",
            {"entity_id": HS_FAN_ENTITY, "percentage": percentage},
            blocking=True,
        )

        assert len(client.async_send_command.call_args_list) == 1
        args = client.async_send_command.call_args[0][0]
        assert args["command"] == "node.set_value"
        assert args["nodeId"] == 39
        assert args["value"] == zwave_speed

        client.async_send_command.reset_mock()

    await assert_percentage_to_zwave_speed(0, 0)
    await assert_percentage_to_zwave_speed(1, 33)
    await assert_percentage_to_zwave_speed(31, 33)
    await assert_percentage_to_zwave_speed(32, 33)
    await assert_percentage_to_zwave_speed(33, 33)
    await assert_percentage_to_zwave_speed(34, 66)
    await assert_percentage_to_zwave_speed(66, 66)
    await assert_percentage_to_zwave_speed(67, 66)
    await assert_percentage_to_zwave_speed(68, 99)
    await assert_percentage_to_zwave_speed(99, 99)
    await assert_percentage_to_zwave_speed(100, 99)

    async def assert_zwave_speed_to_percentage(zwave_speed, percentage):
        """Assert that a ZWave speed is translated to a specific percentage."""
        event = Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": 39,
                "args": {
                    "commandClassName": "Multilevel Switch",
                    "commandClass": 38,
                    "endpoint": 0,
                    "property": "currentValue",
                    "newValue": zwave_speed,
                    "prevValue": 0,
                    "propertyName": "currentValue",
                },
            },
        )
        hs_fc200.receive_event(event)

        state = hass.states.get(HS_FAN_ENTITY)
        assert state.attributes[ATTR_PERCENTAGE] == percentage

    await assert_zwave_speed_to_percentage(0, 0)
    await assert_zwave_speed_to_percentage(1, 33)
    await assert_zwave_speed_to_percentage(32, 33)
    await assert_zwave_speed_to_percentage(33, 33)
    await assert_zwave_speed_to_percentage(34, 67)
    await assert_zwave_speed_to_percentage(66, 67)
    await assert_zwave_speed_to_percentage(67, 100)
    await assert_zwave_speed_to_percentage(99, 100)

    state = hass.states.get(HS_FAN_ENTITY)
    assert math.isclose(state.attributes[ATTR_PERCENTAGE_STEP], 33.3333, rel_tol=1e-3)
