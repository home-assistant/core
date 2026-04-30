"""Provide info to system health."""

from __future__ import annotations

from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import DucoConfigEntry


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    config_entries: list[DucoConfigEntry] = hass.config_entries.async_loaded_entries(
        DOMAIN
    )

    info: dict[str, Any] = {"loaded_config_entries": len(config_entries)}

    # The remaining write-request quota belongs to a specific Duco box. Expose
    # it only when exactly one loaded config entry exists so the value is not
    # ambiguous when multiple devices are configured.
    if len(config_entries) != 1:
        return info

    config_entry = config_entries[0]

    # Exposed via system_health rather than as a diagnostic entity because it
    # reflects the state of how the integration communicates with the device
    # (API quota), not a device-internal subsystem state.
    info["write_requests_remaining"] = (
        config_entry.runtime_data.client.async_get_write_req_remaining()
    )
    return info
