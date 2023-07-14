"""Test the Z-Wave JS number platform."""
from unittest.mock import MagicMock

from zwave_js_server.const import CURRENT_VALUE_PROPERTY, CommandClass
from zwave_js_server.event import Event
from zwave_js_server.model.node import Node

from homeassistant.components.zwave_js.helpers import ZwaveValueMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from .common import replace_value_of_zwave_value

DEFAULT_TONE_SELECT_ENTITY = "select.indoor_siren_6_default_tone_2"
PROTECTION_SELECT_ENTITY = "select.family_room_combo_local_protection_state"
MULTILEVEL_SWITCH_SELECT_ENTITY = "select.front_door_siren"


async def test_default_tone_select(
    hass: HomeAssistant,
    client: MagicMock,
    aeotec_zw164_siren: Node,
    integration: ConfigEntry,
) -> None:
    """Test the default tone select entity."""
    node = aeotec_zw164_siren
    state = hass.states.get(DEFAULT_TONE_SELECT_ENTITY)

    assert state
    assert state.state == "17ALAR~1 (35 sec)"
    attr = state.attributes
    assert attr["options"] == [
        "01DING~1 (5 sec)",
        "02DING~1 (9 sec)",
        "03TRAD~1 (11 sec)",
        "04ELEC~1 (2 sec)",
        "05WEST~1 (13 sec)",
        "06CHIM~1 (7 sec)",
        "07CUCK~1 (31 sec)",
        "08TRAD~1 (6 sec)",
        "09SMOK~1 (11 sec)",
        "10SMOK~1 (6 sec)",
        "11FIRE~1 (35 sec)",
        "12COSE~1 (5 sec)",
        "13KLAX~1 (38 sec)",
        "14DEEP~1 (41 sec)",
        "15WARN~1 (37 sec)",
        "16TORN~1 (46 sec)",
        "17ALAR~1 (35 sec)",
        "18DEEP~1 (62 sec)",
        "19ALAR~1 (15 sec)",
        "20ALAR~1 (7 sec)",
        "21DIGI~1 (8 sec)",
        "22ALER~1 (64 sec)",
        "23SHIP~1 (4 sec)",
        "25CHRI~1 (4 sec)",
        "26GONG~1 (12 sec)",
        "27SING~1 (1 sec)",
        "28TONA~1 (5 sec)",
        "29UPWA~1 (2 sec)",
        "30DOOR~1 (27 sec)",
    ]

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get(DEFAULT_TONE_SELECT_ENTITY)

    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.CONFIG

    # Test select option with string value
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": DEFAULT_TONE_SELECT_ENTITY, "option": "30DOOR~1 (27 sec)"},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "endpoint": 2,
        "commandClass": 121,
        "property": "defaultToneId",
    }
    assert args["value"] == 30

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
                "property": "defaultToneId",
                "newValue": 30,
                "prevValue": 17,
                "propertyName": "defaultToneId",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(DEFAULT_TONE_SELECT_ENTITY)
    assert state
    assert state.state == "30DOOR~1 (27 sec)"


async def test_protection_select(
    hass: HomeAssistant,
    client: MagicMock,
    inovelli_lzw36: Node,
    integration: ConfigEntry,
) -> None:
    """Test the default tone select entity."""
    node = inovelli_lzw36
    state = hass.states.get(PROTECTION_SELECT_ENTITY)

    assert state
    assert state.state == "Unprotected"
    attr = state.attributes
    assert attr["options"] == [
        "Unprotected",
        "ProtectedBySequence",
        "NoOperationPossible",
    ]

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get(PROTECTION_SELECT_ENTITY)

    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.CONFIG

    # Test select option with string value
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": PROTECTION_SELECT_ENTITY, "option": "ProtectedBySequence"},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 117,
        "property": "local",
    }
    assert args["value"] == 1

    client.async_send_command.reset_mock()

    # Test value update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Protection",
                "commandClass": 117,
                "endpoint": 0,
                "property": "local",
                "newValue": 1,
                "prevValue": 0,
                "propertyName": "local",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(PROTECTION_SELECT_ENTITY)
    assert state
    assert state.state == "ProtectedBySequence"

    # Test null value
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Protection",
                "commandClass": 117,
                "endpoint": 0,
                "property": "local",
                "newValue": None,
                "prevValue": 1,
                "propertyName": "local",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(PROTECTION_SELECT_ENTITY)
    assert state
    assert state.state == STATE_UNKNOWN


async def test_multilevel_switch_select(
    hass: HomeAssistant, client, fortrezz_ssa1_siren, integration
) -> None:
    """Test Multilevel Switch CC based select entity."""
    node = fortrezz_ssa1_siren
    state = hass.states.get(MULTILEVEL_SWITCH_SELECT_ENTITY)

    assert state
    assert state.state == "Off"
    attr = state.attributes
    assert attr["options"] == [
        "Off",
        "Strobe ONLY",
        "Siren ONLY",
        "Siren & Strobe FULL Alarm",
    ]

    # Test select option with string value
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": MULTILEVEL_SWITCH_SELECT_ENTITY, "option": "Strobe ONLY"},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 38,
        "property": "targetValue",
    }
    assert args["value"] == 33

    client.async_send_command.reset_mock()

    # Test value update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Multilevel Switch",
                "commandClass": 38,
                "endpoint": 0,
                "property": "currentValue",
                "newValue": 33,
                "prevValue": 0,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(MULTILEVEL_SWITCH_SELECT_ENTITY)
    assert state.state == "Strobe ONLY"


async def test_multilevel_switch_select_no_value(
    hass: HomeAssistant, client, fortrezz_ssa1_siren_state, integration
) -> None:
    """Test Multilevel Switch CC based select entity with primary value is None."""
    node_state = replace_value_of_zwave_value(
        fortrezz_ssa1_siren_state,
        [
            ZwaveValueMatcher(
                property_=CURRENT_VALUE_PROPERTY,
                command_class=CommandClass.SWITCH_MULTILEVEL,
            )
        ],
        None,
    )
    node = Node(client, node_state)
    client.driver.controller.emit("node added", {"node": node})
    await hass.async_block_till_done()

    state = hass.states.get(MULTILEVEL_SWITCH_SELECT_ENTITY)

    assert state
    assert state.state == STATE_UNKNOWN


async def test_config_parameter_select(
    hass: HomeAssistant, climate_adc_t3000, integration
) -> None:
    """Test config parameter select is created."""
    select_entity_id = "select.adc_t3000_hvac_system_type"
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(select_entity_id)
    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.entity_category == EntityCategory.CONFIG

    updated_entry = ent_reg.async_update_entity(
        select_entity_id, **{"disabled_by": None}
    )
    assert updated_entry != entity_entry
    assert updated_entry.disabled is False

    # reload integration and check if entity is correctly there
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(select_entity_id)
    assert state
    assert state.state == "Normal"
