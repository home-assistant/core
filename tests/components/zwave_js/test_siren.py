"""Test the Z-Wave JS siren platform."""
from zwave_js_server.event import Event

from homeassistant.components.siren import ATTR_TONE, ATTR_VOLUME_LEVEL
from homeassistant.const import STATE_OFF, STATE_ON

SIREN_ENTITY = "siren.indoor_siren_6_2"

TONE_ID_VALUE_ID = {
    "endpoint": 2,
    "commandClass": 121,
    "commandClassName": "Sound Switch",
    "property": "toneId",
    "propertyName": "toneId",
    "ccVersion": 1,
    "metadata": {
        "type": "number",
        "readable": True,
        "writeable": True,
        "label": "Play Tone",
        "min": 0,
        "max": 30,
        "states": {
            "0": "off",
            "1": "01DING~1 (5 sec)",
            "2": "02DING~1 (9 sec)",
            "3": "03TRAD~1 (11 sec)",
            "4": "04ELEC~1 (2 sec)",
            "5": "05WEST~1 (13 sec)",
            "6": "06CHIM~1 (7 sec)",
            "7": "07CUCK~1 (31 sec)",
            "8": "08TRAD~1 (6 sec)",
            "9": "09SMOK~1 (11 sec)",
            "10": "10SMOK~1 (6 sec)",
            "11": "11FIRE~1 (35 sec)",
            "12": "12COSE~1 (5 sec)",
            "13": "13KLAX~1 (38 sec)",
            "14": "14DEEP~1 (41 sec)",
            "15": "15WARN~1 (37 sec)",
            "16": "16TORN~1 (46 sec)",
            "17": "17ALAR~1 (35 sec)",
            "18": "18DEEP~1 (62 sec)",
            "19": "19ALAR~1 (15 sec)",
            "20": "20ALAR~1 (7 sec)",
            "21": "21DIGI~1 (8 sec)",
            "22": "22ALER~1 (64 sec)",
            "23": "23SHIP~1 (4 sec)",
            "25": "25CHRI~1 (4 sec)",
            "26": "26GONG~1 (12 sec)",
            "27": "27SING~1 (1 sec)",
            "28": "28TONA~1 (5 sec)",
            "29": "29UPWA~1 (2 sec)",
            "30": "30DOOR~1 (27 sec)",
            "255": "default",
        },
        "valueChangeOptions": ["volume"],
    },
}


async def test_siren(hass, client, aeotec_zw164_siren, integration):
    """Test the siren entity."""
    node = aeotec_zw164_siren
    state = hass.states.get(SIREN_ENTITY)

    assert state
    assert state.state == STATE_OFF

    # Test turn on with default
    await hass.services.async_call(
        "siren",
        "turn_on",
        {"entity_id": SIREN_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == TONE_ID_VALUE_ID
    assert args["value"] == 255

    client.async_send_command.reset_mock()

    # Test turn on with specific tone name and volume level
    await hass.services.async_call(
        "siren",
        "turn_on",
        {
            "entity_id": SIREN_ENTITY,
            ATTR_TONE: "01DING~1 (5 sec)",
            ATTR_VOLUME_LEVEL: 0.5,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == TONE_ID_VALUE_ID
    assert args["value"] == 1
    assert args["options"] == {"volume": 50}

    client.async_send_command.reset_mock()

    # Test turn off
    await hass.services.async_call(
        "siren",
        "turn_off",
        {"entity_id": SIREN_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == TONE_ID_VALUE_ID
    assert args["value"] == 0

    client.async_send_command.reset_mock()

    # Test value update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Sound Switch",
                "commandClass": 121,
                "endpoint": 2,
                "property": "toneId",
                "newValue": 255,
                "prevValue": 0,
                "propertyName": "toneId",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(SIREN_ENTITY)
    assert state.state == STATE_ON
