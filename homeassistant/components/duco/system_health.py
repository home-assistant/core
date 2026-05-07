"""Provide info to system health."""

from typing import Any

from duco.exceptions import DucoConnectionError

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


async def _async_get_write_requests_remaining(
    config_entry: DucoConfigEntry,
) -> int | dict[str, str]:
    """Get the remaining write-request quota for system health."""
    try:
        return await config_entry.runtime_data.client.async_get_write_req_remaining()
    except DucoConnectionError:
        return {"type": "failed", "error": "unreachable"}


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    config_entries: list[DucoConfigEntry] = hass.config_entries.async_loaded_entries(
        DOMAIN
    )

    # The remaining write-request quota belongs to a specific Duco box. Expose
    # it only when exactly one loaded config entry exists so the value is not
    # ambiguous when multiple devices are configured.
    if len(config_entries) != 1:
        return {}

    config_entry = config_entries[0]

    # Exposed via system_health rather than as a diagnostic entity because it
    # reflects the state of how the integration communicates with the device
    # (API quota), not a device-internal subsystem state.
    # Wrap the live quota fetch here because system health only bounds the
    # initial info callback. Returned coroutines are awaited later without a
    # per-field timeout.
    return {
        "write_requests_remaining": _async_get_write_requests_remaining(config_entry)
    }
