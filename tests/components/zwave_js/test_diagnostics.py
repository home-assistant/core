"""Test the Z-Wave JS diagnostics."""
import copy
from unittest.mock import patch

import pytest
from zwave_js_server.const import CommandClass
from zwave_js_server.event import Event
from zwave_js_server.model.node import Node

from homeassistant.components.zwave_js.diagnostics import (
    REDACTED,
    ZwaveValueMatcher,
    async_get_device_diagnostics,
)
from homeassistant.components.zwave_js.discovery import async_discover_node_values
from homeassistant.components.zwave_js.helpers import (
    get_device_id,
    get_value_id_from_unique_id,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import PROPERTY_ULTRAVIOLET

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    integration,
    config_entry_diagnostics,
    config_entry_diagnostics_redacted,
) -> None:
    """Test the config entry level diagnostics data dump."""
    with patch(
        "homeassistant.components.zwave_js.diagnostics.dump_msgs",
        return_value=config_entry_diagnostics,
    ):
        diagnostics = await get_diagnostics_for_config_entry(
            hass, hass_client, integration
        )
        assert diagnostics == config_entry_diagnostics_redacted


async def test_device_diagnostics(
    hass: HomeAssistant,
    client,
    multisensor_6,
    integration,
    hass_client: ClientSessionGenerator,
    version_state,
) -> None:
    """Test the device level diagnostics data dump."""
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(
        identifiers={get_device_id(client.driver, multisensor_6)}
    )
    assert device

    # Create mock config entry for fake entity
    mock_config_entry = MockConfigEntry(domain="test_integration")
    mock_config_entry.add_to_hass(hass)

    # Add an entity entry to the device that is not part of this config entry
    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create(
        "test",
        "test_integration",
        "test_unique_id",
        suggested_object_id="unrelated_entity",
        config_entry=mock_config_entry,
        device_id=device.id,
    )
    assert ent_reg.async_get("test.unrelated_entity")

    # Update a value and ensure it is reflected in the node state
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": multisensor_6.node_id,
            "args": {
                "commandClassName": "Multilevel Sensor",
                "commandClass": 49,
                "endpoint": 0,
                "property": PROPERTY_ULTRAVIOLET,
                "newValue": 1,
                "prevValue": 0,
                "propertyName": PROPERTY_ULTRAVIOLET,
            },
        },
    )
    multisensor_6.receive_event(event)

    diagnostics_data = await get_diagnostics_for_device(
        hass, hass_client, integration, device
    )
    assert diagnostics_data["versionInfo"] == {
        "driverVersion": version_state["driverVersion"],
        "serverVersion": version_state["serverVersion"],
        "minSchemaVersion": 0,
        "maxSchemaVersion": 0,
    }
    # Assert that we only have the entities that were discovered for this device
    # Entities that are created outside of discovery (e.g. node status sensor and
    # ping button) as well as helper entities created from other integrations should
    # not be in dump.
    assert len(diagnostics_data["entities"]) == len(
        list(async_discover_node_values(multisensor_6, device, {device.id: set()}))
    )
    assert any(
        entity.entity_id == "test.unrelated_entity"
        for entity in er.async_entries_for_device(ent_reg, device.id)
    )
    # Explicitly check that the entity that is not part of this config entry is not
    # in the dump.
    assert not any(
        entity["entity_id"] == "test.unrelated_entity"
        for entity in diagnostics_data["entities"]
    )
    assert diagnostics_data["state"] == {
        **multisensor_6.data,
        "values": {id: val.data for id, val in multisensor_6.values.items()},
        "endpoints": {
            str(idx): endpoint.data for idx, endpoint in multisensor_6.endpoints.items()
        },
    }


async def test_device_diagnostics_error(hass: HomeAssistant, integration) -> None:
    """Test the device diagnostics raises exception when an invalid device is used."""
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id, identifiers={("test", "test")}
    )
    with pytest.raises(ValueError):
        await async_get_device_diagnostics(hass, integration, device)


async def test_empty_zwave_value_matcher() -> None:
    """Test empty ZwaveValueMatcher is invalid."""
    with pytest.raises(ValueError):
        ZwaveValueMatcher()


async def test_device_diagnostics_missing_primary_value(
    hass: HomeAssistant,
    client,
    multisensor_6,
    integration,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that device diagnostics handles an entity with a missing primary value."""
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(
        identifiers={get_device_id(client.driver, multisensor_6)}
    )
    assert device

    entity_id = "sensor.multisensor_6_air_temperature"
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(entity_id)

    # check that the primary value for the entity exists in the diagnostics
    diagnostics_data = await get_diagnostics_for_device(
        hass, hass_client, integration, device
    )

    value = multisensor_6.values.get(get_value_id_from_unique_id(entry.unique_id))
    assert value

    air_entity = next(
        x for x in diagnostics_data["entities"] if x["entity_id"] == entity_id
    )

    assert air_entity["value_id"] == value.value_id
    assert air_entity["primary_value"] == {
        "command_class": value.command_class,
        "command_class_name": value.command_class_name,
        "endpoint": value.endpoint,
        "property": value.property_,
        "property_name": value.property_name,
        "property_key": value.property_key,
        "property_key_name": value.property_key_name,
    }

    # make the entity's primary value go missing
    event = Event(
        type="value removed",
        data={
            "source": "node",
            "event": "value removed",
            "nodeId": multisensor_6.node_id,
            "args": {
                "commandClassName": value.command_class_name,
                "commandClass": value.command_class,
                "endpoint": value.endpoint,
                "property": value.property_,
                "prevValue": 0,
                "propertyName": value.property_name,
            },
        },
    )
    multisensor_6.receive_event(event)

    diagnostics_data = await get_diagnostics_for_device(
        hass, hass_client, integration, device
    )

    air_entity = next(
        x for x in diagnostics_data["entities"] if x["entity_id"] == entity_id
    )

    assert air_entity["value_id"] == value.value_id
    assert air_entity["primary_value"] is None


async def test_device_diagnostics_secret_value(
    hass: HomeAssistant,
    client,
    multisensor_6_state,
    integration,
    hass_client: ClientSessionGenerator,
    version_state,
) -> None:
    """Test that secret value in device level diagnostics gets redacted."""

    def _find_ultraviolet_val(data: dict) -> dict:
        """Find ultraviolet property value in data."""
        return next(
            val
            for val in (
                data["values"]
                if isinstance(data["values"], list)
                else data["values"].values()
            )
            if val["commandClass"] == CommandClass.SENSOR_MULTILEVEL
            and val["property"] == PROPERTY_ULTRAVIOLET
        )

    node_state = copy.deepcopy(multisensor_6_state)
    # Force a value to be secret so we can check if it gets redacted
    secret_value = _find_ultraviolet_val(node_state)
    secret_value["metadata"]["secret"] = True
    node = Node(client, node_state)
    client.driver.controller.nodes[node.node_id] = node
    client.driver.controller.emit("node added", {"node": node})
    await hass.async_block_till_done()
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={get_device_id(client.driver, node)})
    assert device

    diagnostics_data = await get_diagnostics_for_device(
        hass, hass_client, integration, device
    )
    test_value = _find_ultraviolet_val(diagnostics_data["state"])
    assert test_value["value"] == REDACTED
