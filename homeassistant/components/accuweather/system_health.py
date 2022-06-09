"""Provide info to system health."""
from __future__ import annotations

from typing import Any

from accuweather.const import ENDPOINT

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
    remaining_requests = list(hass.data[DOMAIN].values())[
        0
    ].accuweather.requests_remaining

    return {
        "can_reach_server": system_health.async_check_can_reach_url(hass, ENDPOINT),
        "remaining_requests": remaining_requests,
    }
