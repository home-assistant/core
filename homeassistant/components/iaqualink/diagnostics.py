"""Diagnostics platform for iAquaLink."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import AqualinkConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AqualinkConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    systems = {}
    for serial, coordinator in entry.runtime_data.coordinators.items():
        systems[serial] = {
            "name": coordinator.system.name,
            "online": coordinator.system.online,
            "data": coordinator.system.data,
            "devices": {
                name: {"class": obj.__class__.__name__, "data": obj.data}
                for name, obj in coordinator.system.devices.items()
            },
        }

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "systems": systems,
    }
