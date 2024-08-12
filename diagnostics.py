"""Provide diagnostics for Matter."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from chip.clusters import Objects
from matter_server.common.helpers.util import dataclass_to_dict, parse_attribute_path

from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .helpers import get_matter, get_node_from_device_entry

ATTRIBUTES_TO_REDACT = {Objects.BasicInformation.Attributes.Location}


def redact_matter_attributes(node_data: dict[str, Any]) -> dict[str, Any]:
    """Redact Matter cluster attribute."""
    redacted = deepcopy(node_data)
    for attribute_to_redact in ATTRIBUTES_TO_REDACT:
        for attribute_path in redacted["attributes"]:
            _, cluster_id, attribute_id = parse_attribute_path(attribute_path)
            if cluster_id != attribute_to_redact.cluster_id:
                continue
            if attribute_id != attribute_to_redact.attribute_id:
                continue
            redacted["attributes"][attribute_path] = REDACTED

    return redacted


def remove_serialization_type(data: dict[str, Any]) -> dict[str, Any]:
    """Remove serialization type from data."""
    if "_type" in data:
        data.pop("_type")
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    matter = get_matter(hass)
    server_diagnostics = await matter.matter_client.get_diagnostics()
    data = dataclass_to_dict(server_diagnostics)
    nodes = [redact_matter_attributes(node_data) for node_data in data["nodes"]]
    data["nodes"] = nodes

    return {"server": data}


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: dr.DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    matter = get_matter(hass)
    server_diagnostics = await matter.matter_client.get_diagnostics()
    node = get_node_from_device_entry(hass, device)

    return {
        "server_info": dataclass_to_dict(server_diagnostics.info),
        "node": redact_matter_attributes(
            remove_serialization_type(dataclass_to_dict(node.node_data) if node else {})
        ),
    }
