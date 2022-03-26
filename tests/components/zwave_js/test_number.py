"""Test the Z-Wave JS number platform."""
from zwave_js_server.event import Event

from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers import entity_registry as er

from .common import BASIC_NUMBER_ENTITY

NUMBER_ENTITY = "number.thermostat_hvac_valve_control"
VOLUME_NUMBER_ENTITY = "number.indoor_siren_6_default_volume_2"


async def test_number(hass, client, aeotec_radiator_thermostat, integration):
    """Test the number entity."""
    node = aeotec_radiator_thermostat
    state = hass.states.get(NUMBER_ENTITY)

    assert state
    assert state.state == "75.0"

    # Test turn on setting value
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": NUMBER_ENTITY, "value": 30},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 4
    assert args["valueId"] == {
        "commandClassName": "Multilevel Switch",
        "commandClass": 38,
        "ccVersion": 1,
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
    assert args["value"] == 30.0

    client.async_send_command.reset_mock()

    # Test value update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 4,
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

    state = hass.states.get(NUMBER_ENTITY)
    assert state.state == "99.0"


async def test_volume_number(hass, client, aeotec_zw164_siren, integration):
    """Test the volume number entity."""
    node = aeotec_zw164_siren
    state = hass.states.get(VOLUME_NUMBER_ENTITY)

    assert state
    assert state.state == "1.0"
    assert state.attributes["step"] == 0.01
    assert state.attributes["max"] == 1.0
    assert state.attributes["min"] == 0

    # Test turn on setting value
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": VOLUME_NUMBER_ENTITY, "value": 0.3},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "endpoint": 2,
        "commandClass": 121,
        "commandClassName": "Sound Switch",
        "property": "defaultVolume",
        "propertyName": "defaultVolume",
        "ccVersion": 1,
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "label": "Default volume",
            "min": 0,
            "max": 100,
            "unit": "%",
        },
        "value": 100,
    }
    assert args["value"] == 30

    client.async_send_command.reset_mock()

    # Test value update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 4,
            "args": {
                "commandClassName": "Sound Switch",
                "commandClass": 121,
                "endpoint": 2,
                "property": "defaultVolume",
                "newValue": 30,
                "prevValue": 100,
                "propertyName": "defaultVolume",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(VOLUME_NUMBER_ENTITY)
    assert state.state == "0.3"

    # Test null value
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 4,
            "args": {
                "commandClassName": "Sound Switch",
                "commandClass": 121,
                "endpoint": 2,
                "property": "defaultVolume",
                "newValue": None,
                "prevValue": 30,
                "propertyName": "defaultVolume",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(VOLUME_NUMBER_ENTITY)
    assert state.state == STATE_UNKNOWN


async def test_disabled_basic_number(hass, ge_in_wall_dimmer_switch, integration):
    """Test number is created from Basic CC and is disabled."""
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(BASIC_NUMBER_ENTITY)

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
