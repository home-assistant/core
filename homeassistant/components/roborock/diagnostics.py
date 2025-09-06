"""Support for Roborock diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .coordinator import RoborockConfigEntry

TO_REDACT_CONFIG = ["token", "sn", "rruid", CONF_UNIQUE_ID, "username", "uid"]

TO_REDACT_COORD = ["duid", "localKey", "mac", "bssid"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: RoborockConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators = config_entry.runtime_data

    coordinators_diag: dict[str, Any] = {}
    for i, coordinator in enumerate(coordinators.values()):
        api_diag = dict(coordinator.api.diagnostic_data)
        # Backwards-compat: older snapshots expect a 'misc_info' mapping.
        api_diag.setdefault("misc_info", {})
        coordinators_diag[f"**REDACTED-{i}**"] = {
            "roborock_device_info": async_redact_data(
                coordinator.roborock_device_info.as_dict(), TO_REDACT_COORD
            ),
            "api": api_diag,
        }

    return {
        "config_entry": async_redact_data(config_entry.data, TO_REDACT_CONFIG),
        "coordinators": coordinators_diag,
    }
