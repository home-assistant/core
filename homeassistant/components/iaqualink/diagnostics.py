"""Diagnostics platform for iAquaLink."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import AqualinkConfigEntry

TO_REDACT = {"serial", "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AqualinkConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    systems = []
    for serial, coordinator in entry.runtime_data.coordinators.items():
        systems.append(
            {
                "serial_number": serial,
                "name": coordinator.system.name,
                "online": coordinator.system.online,
                "data": coordinator.system.data,
                "devices": {
                    name: {"class": obj.__class__.__name__, "data": obj.data}
                    for name, obj in getattr(coordinator.system, "devices", {}).items()
                },
            }
        )

    return {"systems": async_redact_data(systems, TO_REDACT)}
