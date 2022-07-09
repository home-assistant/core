"""Provides diagnostics for Z-Wave JS."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import astuple, dataclass
from typing import Any

from zwave_js_server.client import Client
from zwave_js_server.const import CommandClass
from zwave_js_server.dump import dump_msgs
from zwave_js_server.model.node import Node, NodeDataType
from zwave_js_server.model.value import ValueDataType

from homeassistant.components.diagnostics.const import REDACTED
from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DATA_CLIENT, DOMAIN
from .helpers import (
    get_home_and_node_id_from_device_entry,
    get_state_key_from_unique_id,
    get_value_id_from_unique_id,
)


@dataclass
class ZwaveValueMatcher:
    """Class to allow matching a Z-Wave Value."""

    property_: str | int | None = None
    command_class: int | None = None
    endpoint: int | None = None
    property_key: str | int | None = None

    def __post_init__(self) -> None:
        """Post initialization check."""
        if all(val is None for val in astuple(self)):
            raise ValueError("At least one of the fields must be set.")


KEYS_TO_REDACT = {"homeId", "location"}

VALUES_TO_REDACT = (
    ZwaveValueMatcher(property_="userCode", command_class=CommandClass.USER_CODE),
)


def redact_value_of_zwave_value(zwave_value: ValueDataType) -> ValueDataType:
    """Redact value of a Z-Wave value."""
    for value_to_redact in VALUES_TO_REDACT:
        command_class = None
        if "commandClass" in zwave_value:
            command_class = CommandClass(zwave_value["commandClass"])
        zwave_value_id = ZwaveValueMatcher(
            property_=zwave_value.get("property"),
            command_class=command_class,
            endpoint=zwave_value.get("endpoint"),
            property_key=zwave_value.get("propertyKey"),
        )
        if all(
            redacted_field_val is None or redacted_field_val == zwave_value_field_val
            for redacted_field_val, zwave_value_field_val in zip(
                astuple(value_to_redact), astuple(zwave_value_id)
            )
        ):
            redacted_value: ValueDataType = deepcopy(zwave_value)
            redacted_value["value"] = REDACTED
            return redacted_value
    return zwave_value


def redact_node_state(node_state: NodeDataType) -> NodeDataType:
    """Redact node state."""
    redacted_state: NodeDataType = deepcopy(node_state)
    redacted_state["values"] = [
        redact_value_of_zwave_value(zwave_value) for zwave_value in node_state["values"]
    ]
    return redacted_state


def get_device_entities(
    hass: HomeAssistant, node: Node, device: dr.DeviceEntry
) -> list[dict[str, Any]]:
    """Get entities for a device."""
    entity_entries = er.async_entries_for_device(
        er.async_get(hass), device.id, include_disabled_entities=True
    )
    entities = []
    for entry in entity_entries:
        # If the value ID returns as None, we don't need to include this entity
        if (value_id := get_value_id_from_unique_id(entry.unique_id)) is None:
            continue

        primary_value_data = None
        if (zwave_value := node.values.get(value_id)) is not None:
            primary_value_data = {
                "command_class": zwave_value.command_class,
                "command_class_name": zwave_value.command_class_name,
                "endpoint": zwave_value.endpoint,
                "property": zwave_value.property_,
                "property_name": zwave_value.property_name,
                "property_key": zwave_value.property_key,
                "property_key_name": zwave_value.property_key_name,
            }

            state_key = get_state_key_from_unique_id(entry.unique_id)
            if state_key is not None:
                primary_value_data["state_key"] = state_key

        entity = {
            "domain": entry.domain,
            "entity_id": entry.entity_id,
            "original_name": entry.original_name,
            "original_device_class": entry.original_device_class,
            "disabled": entry.disabled,
            "disabled_by": entry.disabled_by,
            "hidden_by": entry.hidden_by,
            "original_icon": entry.original_icon,
            "entity_category": entry.entity_category,
            "supported_features": entry.supported_features,
            "unit_of_measurement": entry.unit_of_measurement,
            "primary_value": primary_value_data,
        }
        entities.append(entity)
    return entities


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> list[dict]:
    """Return diagnostics for a config entry."""
    msgs: list[dict] = async_redact_data(
        await dump_msgs(config_entry.data[CONF_URL], async_get_clientsession(hass)),
        KEYS_TO_REDACT,
    )
    handshake_msgs = msgs[:-1]
    network_state = msgs[-1]
    network_state["result"]["state"]["nodes"] = [
        redact_node_state(node) for node in network_state["result"]["state"]["nodes"]
    ]
    return [*handshake_msgs, network_state]


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: dr.DeviceEntry
) -> dict:
    """Return diagnostics for a device."""
    client: Client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
    identifiers = get_home_and_node_id_from_device_entry(device)
    node_id = identifiers[1] if identifiers else None
    assert (driver := client.driver)
    if node_id is None or node_id not in driver.controller.nodes:
        raise ValueError(f"Node for device {device.id} can't be found")
    node = driver.controller.nodes[node_id]
    entities = get_device_entities(hass, node, device)
    assert client.version
    node_state = redact_node_state(async_redact_data(node.data, KEYS_TO_REDACT))
    node_state["statistics"] = node.statistics.data
    return {
        "versionInfo": {
            "driverVersion": client.version.driver_version,
            "serverVersion": client.version.server_version,
            "minSchemaVersion": client.version.min_schema_version,
            "maxSchemaVersion": client.version.max_schema_version,
        },
        "entities": entities,
        "state": node_state,
    }
