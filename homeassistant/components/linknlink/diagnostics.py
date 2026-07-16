"""Diagnostics support for LinknLink."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .coordinator import LinknLinkConfigEntry

TO_REDACT = {
    CONF_HOST,
    CONF_MAC,
    CONF_UNIQUE_ID,
    "did",
    "device_id",
    "id",
    "ip",
    "last_error",
    "mac",
    "source_ip",
    "targets",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LinknLinkConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a LinknLink config entry."""
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return async_redact_data(
            {
                "config_entry": entry.as_dict(),
                "device": None,
                "position_subscription": None,
                "environment_state": None,
                "environment_available": False,
                "last_update_success": False,
            },
            TO_REDACT,
        )
    return async_redact_data(
        {
            "config_entry": entry.as_dict(),
            "device": asdict(coordinator.device),
            "position_subscription": (
                asdict(coordinator.position_state)
                if coordinator.position_state is not None
                else None
            ),
            "environment_state": (
                {
                    **asdict(coordinator.environment_state),
                    "available_fields": sorted(
                        coordinator.environment_state.available_fields
                    ),
                }
                if coordinator.environment_state is not None
                else None
            ),
            "environment_available": coordinator.environment_available,
            "last_update_success": coordinator.last_update_success,
        },
        TO_REDACT,
    )
