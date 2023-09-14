"""Test the Z-Wave JS number platform."""
from unittest.mock import patch

import pytest
from zwave_js_server.event import Event

from homeassistant.const import STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import BASIC_NUMBER_ENTITY

from tests.common import MockConfigEntry

NUMBER_ENTITY = "number.thermostat_hvac_valve_control"
VOLUME_NUMBER_ENTITY = "number.indoor_siren_6_default_volume_2"


async def test_number(
    hass: HomeAssistant, client, aeotec_radiator_thermostat, integration
) -> None:
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
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
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


@pytest.fixture(name="no_target_value")
def mock_client_fixture():
    """Mock no target_value."""

    with patch(
        "homeassistant.components.zwave_js.number.ZwaveNumberEntity.get_zwave_value",
        return_value=None,
    ):
        yield


async def test_number_no_target_value(
    hass: HomeAssistant,
    client,
    no_target_value,
    aeotec_radiator_thermostat,
    integration,
) -> None:
    """Test the number entity with no target value."""
    # Test turn on setting value fails
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": NUMBER_ENTITY, "value": 30},
            blocking=True,
        )


async def test_number_writeable(
    hass: HomeAssistant, client, aeotec_radiator_thermostat
) -> None:
    """Test the number entity where current value is writeable."""
    aeotec_radiator_thermostat.values["4-38-0-currentValue"].metadata.data[
        "writeable"
    ] = True
    aeotec_radiator_thermostat.values.pop("4-38-0-targetValue")

    # set up config entry
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Test turn on setting value
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": NUMBER_ENTITY, "value": 30},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 4
    assert args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "currentValue",
    }
    assert args["value"] == 30.0

    client.async_send_command.reset_mock()


async def test_volume_number(
    hass: HomeAssistant, client, aeotec_zw164_siren, integration
) -> None:
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
        "property": "defaultVolume",
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


async def test_disabled_basic_number(
    hass: HomeAssistant, ge_in_wall_dimmer_switch, integration
) -> None:
    """Test number is created from Basic CC and is disabled."""
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(BASIC_NUMBER_ENTITY)

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_config_parameter_number(
    hass: HomeAssistant, climate_adc_t3000, integration
) -> None:
    """Test config parameter number is created."""
    number_entity_id = "number.adc_t3000_heat_staging_delay"
    number_with_states_entity_id = "number.adc_t3000_calibration_temperature"
    ent_reg = er.async_get(hass)
    for entity_id in (number_entity_id, number_with_states_entity_id):
        entity_entry = ent_reg.async_get(entity_id)
        assert entity_entry
        assert entity_entry.disabled
        assert entity_entry.entity_category == EntityCategory.CONFIG

    for entity_id in (number_entity_id, number_with_states_entity_id):
        updated_entry = ent_reg.async_update_entity(entity_id, **{"disabled_by": None})
        assert updated_entry != entity_entry
        assert updated_entry.disabled is False

    # reload integration and check if entity is correctly there
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(number_entity_id)
    assert state
    assert state.state == "30.0"
    assert "reserved_values" not in state.attributes

    state = hass.states.get(number_with_states_entity_id)
    assert state
    assert state.state == "0.0"
    assert "reserved_values" in state.attributes
    assert state.attributes["reserved_values"] == {-1: "Disabled"}
