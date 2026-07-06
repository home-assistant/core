"""Diagnostics platform for iAquaLink."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import AqualinkConfigEntry

TO_REDACT = {"serial", "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AqualinkConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    systems = [
        {
            "online": coordinator.system.online,
            "data": {k: v for k, v in coordinator.system.data.items() if k != "name"},
            "devices": {
                name: {"class": obj.__class__.__name__, "data": obj.data}
                for name, obj in (
                    getattr(coordinator.system, "devices", None) or {}
                ).items()
            },
        }
        for coordinator in entry.runtime_data.coordinators.values()
    ]

    return {"systems": async_redact_data(systems, TO_REDACT)}
