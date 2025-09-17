"""Diagnostics platform for Sleep as Android integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import SleepAsAndroidConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: SleepAsAndroidConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "config_entry_data": {"cloudhook": config_entry.data["cloudhook"]},
    }
