"""Diagnostics for the Portainer integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

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
                        "id": container.container.id,
                        "names": list(container.container.names or []),
                        "image": container.container.image,
                        "state": container.container.state,
                        "status": container.container.status,
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
