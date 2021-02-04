"""Provide info to system health."""
from airly import Airly

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass):
    """Get info for the info page."""
    return {
        "can_reach_server": system_health.async_check_can_reach_url(
            hass, Airly.AIRLY_API_URL
        )
    }
