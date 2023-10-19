"""Diagnostics support for La Marzocco."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import LmApiCoordinator

TO_REDACT = {
    "serial_number",
    "machine_sn",
    "machine_name",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: LmApiCoordinator = hass.data[DOMAIN][entry.entry_id]
    # collect all data sources
    data = {}
    data["current_status"] = coordinator.data.current_status
    data["machine_info"] = coordinator.data.machine_info
    data["config"] = coordinator.data.config
    data["statistics"] = coordinator.data.statistics

    # build a firmware section
    data["firmware"] = {}
    data["firmware"]["machine"] = {}
    data["firmware"]["machine"]["version"] = coordinator.data.firmware_version
    data["firmware"]["machine"][
        "latest_version"
    ] = coordinator.data.latest_firmware_version
    data["firmware"]["gateway"] = {}
    data["firmware"]["gateway"]["version"] = coordinator.data.gateway_version
    data["firmware"]["gateway"][
        "latest_version"
    ] = coordinator.data.latest_gateway_version

    return async_redact_data(data, TO_REDACT)
