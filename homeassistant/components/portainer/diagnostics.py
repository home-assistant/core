"""Diagnostics for the Portainer integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from . import PortainerConfigEntry
from .coordinator import PortainerCoordinator

TO_REDACT = [CONF_API_TOKEN]


def _serialize_coordinator(coordinator: PortainerCoordinator) -> dict[str, Any]:
    """Serialize coordinator data into a JSON-safe structure."""

    serialized_endpoints: list[dict[str, Any]] = []
    for endpoint_id, endpoint_data in coordinator.data.items():
        serialized_endpoints.append(
            {
                "id": endpoint_id,
                "name": endpoint_data.name,
                "endpoint": {
                    "status": endpoint_data.endpoint.status,
                    "url": endpoint_data.endpoint.url,
                    "public_url": endpoint_data.endpoint.public_url,
                },
                "containers": [
                    {
                        "id": container.id,
                        "names": list(container.names)
                        if container.names
                        else [],  # Docker names are built-upon asliases as well. Here I include them all. Maybe I should only allow the first record that represents the "main" name?
                        "image": container.image,
                        "state": container.state,
                        "status": container.status,
                    }
                    for container in endpoint_data.containers.values()
                ],
            }
        )

    return {"endpoints": serialized_endpoints}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: PortainerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Portainer config entry."""

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "coordinator": _serialize_coordinator(config_entry.runtime_data),
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: PortainerConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a Portainer device."""
    entity_registry = er.async_get(hass)
    entities = entity_registry.entities.get_entries_for_device_id(device.id, True)

    return {
        "device": async_redact_data(device.dict_repr, TO_REDACT),
        "entities": [
            {
                "entity": entity.as_partial_dict,
                "state": state.as_dict()
                if (state := hass.states.get(entity.entity_id))
                else None,
            }
            for entity in entities
        ],
    }
