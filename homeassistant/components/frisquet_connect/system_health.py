"""Provide info to system health."""

from typing import Any
from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from frisquet_connect.repositories.frisquet_connect_repository import (
    FRISQUET_CONNECT_API_URL,
)


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    return {
        # checking the url can take a while, so set the coroutine in the info dict
        "can_reach_server": system_health.async_check_can_reach_url(
            hass, FRISQUET_CONNECT_API_URL
        ),
    }
