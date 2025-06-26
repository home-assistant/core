"""Diagnostics support for PlayStation Network."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from psnawp_api.models.trophies import PlatformType

from homeassistant.core import HomeAssistant

from .const import CONF_NPSSO
from .coordinator import PlaystationNetworkConfigEntry, PlaystationNetworkCoordinator

TO_REDACT = {
    CONF_NPSSO,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PlaystationNetworkConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: PlaystationNetworkCoordinator = entry.runtime_data

    return {
        "data": _serialize_platform_types(asdict(coordinator.data)),
    }


def _serialize_platform_types(data: Any) -> Any:
    """Recursively convert PlatformType enums to strings in dicts and sets."""
    if isinstance(data, dict):
        return {
            (
                platform.value if isinstance(platform, PlatformType) else platform
            ): _serialize_platform_types(record)
            for platform, record in data.items()
        }
    if isinstance(data, set):
        return [
            record.value if isinstance(record, PlatformType) else record
            for record in data
        ]
    if isinstance(data, PlatformType):
        return data.value
    return data
