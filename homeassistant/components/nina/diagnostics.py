"""Diagnostics for the Nina integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import NinaConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NinaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    runtime_data_dict = {
        region_key: [asdict(warning) for warning in region_data]
        for region_key, region_data in entry.runtime_data.data.items()
    }

    return {
        "entry_data": dict(entry.data),
        "data": runtime_data_dict,
    }
