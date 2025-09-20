"""Provides diagnostics for Tado."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import TadoConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: TadoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Tado config entry."""
    result: dict[str, Any] = {
        "data": config_entry.runtime_data.coordinator.data,
    }

    # Mobile device tracking is optional; include only when available
    mobile_coordinator = getattr(config_entry.runtime_data, "mobile_coordinator", None)
    if mobile_coordinator is not None:
        result["mobile_devices"] = mobile_coordinator.data

    return result
