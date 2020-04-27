"""Test Z-Wave (central) Scenes."""
import asyncio
import json
from unittest.mock import Mock

from .common import async_capture_events, setup_zwave


async def test_scenes(hass, sent_messages):
    """Test setting up config entry."""

    receive_message = await setup_zwave(hass, "generic_network_dump.csv")
    events = async_capture_events(hass, "zwave_mqtt.scene_activated")

    # Publish fake scene event on mqtt
    receive_message(
        Mock(
            topic="OpenZWave/1/node/39/instance/1/commandclass/43/value/562950622511127/",
            payload=json.dumps(
                {
                    "Label": "Scene",
                    "Value": 16,
                    "Units": "",
                    "Min": -2147483648,
                    "Max": 2147483647,
                    "Type": "Int",
                    "Instance": 1,
                    "CommandClass": "COMMAND_CLASS_SCENE_ACTIVATION",
                    "Index": 0,
                    "Node": 7,
                    "Genre": "User",
                    "Help": "",
                    "ValueIDKey": 122339347,
                    "ReadOnly": False,
                    "WriteOnly": False,
                    "ValueSet": False,
                    "ValuePolled": False,
                    "ChangeVerified": False,
                    "Event": "valueChanged",
                    "TimeStamp": 1579630367,
                }
            ),
        )
    )
    # wait for the event
    count = 0
    while count < 5 and not events:
        await asyncio.sleep(0.0)
        count += 1
    assert len(events) == 1
    assert events[0].data["scene_value_id"] == 16

    # Publish fake central scene event on mqtt
    receive_message(
        Mock(
            topic="OpenZWave/1/node/39/instance/1/commandclass/91/value/281476005806100/",
            payload=json.dumps(
                {
                    "Label": "Scene 1",
                    "Value": {
                        "List": [
                            {"Value": 0, "Label": "Inactive"},
                            {"Value": 1, "Label": "Pressed 1 Time"},
                            {"Value": 2, "Label": "Key Released"},
                            {"Value": 3, "Label": "Key Held down"},
                        ],
                        "Selected": "Pressed 1 Time",
                        "Selected_id": 1,
                    },
                    "Units": "",
                    "Min": 0,
                    "Max": 0,
                    "Type": "List",
                    "Instance": 1,
                    "CommandClass": "COMMAND_CLASS_CENTRAL_SCENE",
                    "Index": 1,
                    "Node": 61,
                    "Genre": "User",
                    "Help": "",
                    "ValueIDKey": 281476005806100,
                    "ReadOnly": False,
                    "WriteOnly": False,
                    "ValueSet": False,
                    "ValuePolled": False,
                    "ChangeVerified": False,
                    "Event": "valueChanged",
                    "TimeStamp": 1579640710,
                }
            ),
        )
    )
    # wait for the event
    count = 0
    while count < 5 and len(events) != 2:
        await asyncio.sleep(0.0)
        count += 1
    assert len(events) == 2
    assert events[1].data["scene_id"] == 1
    assert events[1].data["scene_label"] == "Scene 1"
    assert events[1].data["scene_value_label"] == "Pressed 1 Time"
