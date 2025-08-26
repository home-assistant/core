"""Diagnostics support for the Meater integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import MeaterConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: MeaterConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data

    return {
        identifier: {
            "id": probe.id,
            "internal_temperature": probe.internal_temperature,
            "ambient_temperature": probe.ambient_temperature,
            "time_updated": probe.time_updated.isoformat(),
            "cook": (
                {
                    "id": probe.cook.id,
                    "name": probe.cook.name,
                    "state": probe.cook.state,
                    "target_temperature": (
                        probe.cook.target_temperature
                        if hasattr(probe.cook, "target_temperature")
                        else None
                    ),
                    "peak_temperature": (
                        probe.cook.peak_temperature
                        if hasattr(probe.cook, "peak_temperature")
                        else None
                    ),
                    "time_remaining": (
                        probe.cook.time_remaining
                        if hasattr(probe.cook, "time_remaining")
                        else None
                    ),
                    "time_elapsed": (
                        probe.cook.time_elapsed
                        if hasattr(probe.cook, "time_elapsed")
                        else None
                    ),
                }
                if probe.cook
                else None
            ),
        }
        for identifier, probe in coordinator.data.items()
    }
