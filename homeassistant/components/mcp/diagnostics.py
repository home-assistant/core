"""Diagnostics support for the Model Context Protocol integration."""

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

import probatio

from homeassistant.core import HomeAssistant

from .types import ModelContextProtocolConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ModelContextProtocolConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    server_info = coordinator.server_info
    if TYPE_CHECKING:
        assert server_info is not None
    return {
        "authentication": "auth_implementation" in entry.data,
        "server": server_info.model_dump(mode="json", by_alias=True, exclude_none=True),
        "tools": [
            {
                "name": tool.name,
                "title": tool.title,
                "description": tool.description,
                "annotations": asdict(tool.annotations),
                "input_schema": probatio.to_openapi(tool.parameters),
            }
            for tool in coordinator.data
        ],
    }
