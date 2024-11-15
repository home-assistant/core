"""Provide info to system health."""

from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    return {
        "api_endpoint_reachable": system_health.async_check_can_reach_url(
            hass, "https://api.spotify.com"
        )
    }
