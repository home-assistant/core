"""Diagnostics support for Launch Library."""

from __future__ import annotations

from typing import Any

from pylaunches.types import Event, Launch

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import LaunchLibraryData


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry[LaunchLibraryData],
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diagnostics = {}
    if (runtime_data := entry.runtime_data) is None:
        return diagnostics

    def _first_element(data: list[Launch | Event]) -> dict[str, Any] | None:
        if not data:
            return None
        return data[0]

    if (launches := runtime_data["upcoming_launches"].data) is not None:
        diagnostics["next_launch"] = _first_element(launches)

    if (starship := runtime_data["starship_events"].data) is not None:
        diagnostics["starship_launch"] = _first_element(
            starship["upcoming"]["launches"]
        )
        diagnostics["starship_event"] = _first_element(starship["upcoming"]["events"])

    return diagnostics
