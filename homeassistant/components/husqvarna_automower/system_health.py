"""Provide info to system health."""

from __future__ import annotations

from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    entry = hass.config_entries.async_loaded_entries(DOMAIN)[0]
    coordinator = entry.runtime_data

    pong_time = coordinator.pong
    if pong_time is None:
        pong_display = "Never"
    else:
        pong_display = coordinator.pong

    return {
        "last_pong": pong_display,
        "polling": str(coordinator.update_interval is not None),
    }
