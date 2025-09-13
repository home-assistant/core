"""Support for the Airzone diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .coordinator import (
    RoborockConfigEntry,
    RoborockDataUpdateCoordinator,
    RoborockDataUpdateCoordinatorA01,
)

TO_REDACT_CONFIG = ["token", "sn", "rruid", CONF_UNIQUE_ID, "username", "uid"]

TO_REDACT_COORD = ["duid", "localKey", "mac", "bssid"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: RoborockConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators = config_entry.runtime_data

    def _build_api_section(
        coordinator: RoborockDataUpdateCoordinator | RoborockDataUpdateCoordinatorA01,
    ) -> dict[str, Any]:
        diag = getattr(coordinator.api, "diagnostic_data", {}) or {}
        # Keep diagnostics stable: only expose misc_info (as tested via snapshot)
        misc = diag.get("misc_info", {}) if isinstance(diag, dict) else {}
        return {"misc_info": misc}

    return {
        "config_entry": async_redact_data(config_entry.data, TO_REDACT_CONFIG),
        "coordinators": {
            f"**REDACTED-{i}**": {
                "roborock_device_info": async_redact_data(
                    coordinator.roborock_device_info.as_dict(), TO_REDACT_COORD
                ),
                "api": _build_api_section(coordinator),
            }
            for i, coordinator in enumerate(coordinators.values())
        },
    }
