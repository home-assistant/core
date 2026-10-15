"""Diagnostics support for Peblar."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import PeblarConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PeblarConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    return {
        "system_information": runtime_data.system_information.to_dict(),
        "user_configuration": (
            runtime_data.user_configuration_coordinator.data.to_dict()
        ),
        "ev": runtime_data.data_coordinator.data.ev.to_dict(),
        "meter": runtime_data.data_coordinator.data.meter.to_dict(),
        "system": runtime_data.data_coordinator.data.system.to_dict(),
        "versions": {
            "available": (runtime_data.version_coordinator.data.available.to_dict()),
            "current": (runtime_data.version_coordinator.data.current.to_dict()),
        },
    }
