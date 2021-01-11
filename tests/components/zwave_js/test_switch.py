"""Test the Z-Wave JS sensor platform."""

from .common import SWITCH_ENTITY


async def test_switch(hass, binary_switch, integration, client):
    """Test the switch."""
    state = hass.states.get(SWITCH_ENTITY)

    assert state
    assert state.state == "off"

    # Test turning on
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": SWITCH_ENTITY}, blocking=True
    )

    args = client.async_send_json_message.call_args[0][0]
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

    # Test turning off
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": SWITCH_ENTITY}, blocking=True
    )

    args = client.async_send_json_message.call_args[0][0]
    print(args)
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
