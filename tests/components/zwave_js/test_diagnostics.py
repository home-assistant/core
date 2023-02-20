"""Test the Z-Wave JS diagnostics."""
from unittest.mock import patch

import pytest
from zwave_js_server.event import Event

from homeassistant.components.zwave_js.diagnostics import (
    ZwaveValueMatcher,
    async_get_device_diagnostics,
)
from homeassistant.components.zwave_js.discovery import async_discover_node_values
from homeassistant.components.zwave_js.helpers import (
    get_device_id,
    get_value_id_from_unique_id,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as async_get_dev_reg
from homeassistant.helpers.entity_registry import async_get as async_get_ent_reg

from .common import PROPERTY_ULTRAVIOLET

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
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device({get_device_id(client.driver, multisensor_6)})
    assert device

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
    # ping button) should not be in dump.
    assert len(diagnostics_data["entities"]) == len(
        list(async_discover_node_values(multisensor_6, device, {device.id: set()}))
    )
    assert diagnostics_data["state"] == {
        **multisensor_6.data,
        "statistics": {
            "commandsDroppedRX": 0,
            "commandsDroppedTX": 0,
            "commandsRX": 0,
            "commandsTX": 0,
            "timeoutResponse": 0,
        },
    }


async def test_device_diagnostics_error(hass: HomeAssistant, integration) -> None:
    """Test the device diagnostics raises exception when an invalid device is used."""
    dev_reg = async_get_dev_reg(hass)
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
    """Test that the device diagnostics handles an entity with a missing primary value."""
    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device({get_device_id(client.driver, multisensor_6)})
    assert device

    entity_id = "sensor.multisensor_6_air_temperature"
    ent_reg = async_get_ent_reg(hass)
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
