"""Diagnostics support for La Marzocco."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import LaMarzoccoUpdateCoordinator

TO_REDACT = {
    "serial_number",
    "machine_sn",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: LaMarzoccoUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    # collect all data sources
    data = {}
    data["current_status"] = coordinator.lm.current_status
    data["machine_info"] = coordinator.lm.machine_info
    data["config"] = coordinator.lm.config
    data["statistics"] = {"stats": coordinator.lm.statistics}  # wrap to satisfy mypy

    # build a firmware section
    data["firmware"] = {
        "machine": {
            "version": coordinator.lm.firmware_version,
            "latest_version": coordinator.lm.latest_firmware_version,
        },
        "gateway": {
            "version": coordinator.lm.gateway_version,
            "latest_version": coordinator.lm.latest_gateway_version,
        },
    }
    return async_redact_data(data, TO_REDACT)
