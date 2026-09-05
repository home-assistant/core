"""Provide info to system health."""

from typing import Any

from duco_connectivity.exceptions import DucoConnectionError

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
        return (
            await config_entry.runtime_data.client.async_get_write_requests_remaining()
        )
    except DucoConnectionError:
        return {"type": "failed", "error": "unreachable"}


def _entry_write_requests_remaining_key(config_entry: DucoConfigEntry) -> str:
    """Return the identifying label for a config entry quota."""
    identifier = config_entry.unique_id or config_entry.entry_id
    return f"{config_entry.title or config_entry.entry_id} ({identifier})"


async def _async_get_write_requests_remaining_summary(
    config_entries: list[DucoConfigEntry],
) -> str:
    """Get a per-entry write-request summary for system health."""
    # Keep one translated system health label; multiple Duco boxes are
    # summarized in the value to avoid ambiguous per-entry labels.
    summaries: list[str] = []
    for config_entry in config_entries:
        result = await _async_get_write_requests_remaining(config_entry)
        summaries.append(
            f"{_entry_write_requests_remaining_key(config_entry)}: "
            f"{result if not isinstance(result, dict) else f'Failed: {result["error"]}'}"
        )

    return "; ".join(summaries)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    config_entries: list[DucoConfigEntry] = hass.config_entries.async_loaded_entries(
        DOMAIN
    )

    if not config_entries:
        return {}

    if len(config_entries) == 1:
        return {
            "write_requests_remaining": _async_get_write_requests_remaining(
                config_entries[0]
            )
        }

    return {
        "write_requests_remaining": _async_get_write_requests_remaining_summary(
            config_entries
        )
    }
