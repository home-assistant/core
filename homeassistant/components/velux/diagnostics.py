"""Diagnostics support for Velux."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_MAC, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import VeluxConfigEntry

TO_REDACT = {CONF_MAC, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VeluxConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry, includes nodes, devices, and entities."""

    pyvlx = entry.runtime_data

    nodes: list[dict[str, Any]] = [
        {
            "node_id": node.node_id,
            "name": node.name,
            "serial_number": node.serial_number,
            "type": type(node).__name__,
            "device_updated_callbacks": node.device_updated_cbs,
        }
        for node in pyvlx.nodes
    ]

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    devices: list[dict[str, Any]] = []
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        entities: list[dict[str, Any]] = []
        for entity_entry in er.async_entries_for_device(
            entity_registry,
            device_id=device.id,
            include_disabled_entities=True,
        ):
            state_dict = None
            if state := hass.states.get(entity_entry.entity_id):
                state_dict = dict(state.as_dict())
                state_dict.pop("context", None)

            entities.append(
                {
                    "entity_id": entity_entry.entity_id,
                    "unique_id": entity_entry.unique_id,
                    "state": state_dict,
                }
            )

        devices.append(
            {
                "name": device.name,
                "entities": entities,
            }
        )

    return {
        "config_entry": async_redact_data(entry.data, TO_REDACT),
        "connection": {
            "connected": pyvlx.connection.connected,
            "connection_count": pyvlx.connection.connection_counter,
            "frame_received_cbs": pyvlx.connection.frame_received_cbs,
            "connection_opened_cbs": pyvlx.connection.connection_opened_cbs,
            "connection_closed_cbs": pyvlx.connection.connection_closed_cbs,
        },
        "gateway": {
            "state": str(pyvlx.klf200.state) if pyvlx.klf200.state else None,
            "version": str(pyvlx.klf200.version) if pyvlx.klf200.version else None,
            "protocol_version": (
                str(pyvlx.klf200.protocol_version)
                if pyvlx.klf200.protocol_version
                else None
            ),
        },
        "nodes": nodes,
        "devices": devices,
    }
