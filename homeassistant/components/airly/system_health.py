"""Provide info to system health."""

from __future__ import annotations

from typing import Any

from airly import Airly

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import AirlyConfigEntry


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    config_entry: AirlyConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]

    requests_remaining = config_entry.runtime_data.airly.requests_remaining
    requests_per_day = config_entry.runtime_data.airly.requests_per_day

    return {
        "can_reach_server": system_health.async_check_can_reach_url(
            hass, Airly.AIRLY_API_URL
        ),
        "requests_remaining": requests_remaining,
        "requests_per_day": requests_per_day,
    }
