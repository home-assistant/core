"""Provide info to system health."""
from airly import Airly

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass):
    """Get info for the info page."""
    requests_remaining = list(hass.data[DOMAIN].values())[0].airly.requests_remaining
    requests_per_day = list(hass.data[DOMAIN].values())[0].airly.requests_per_day

    return {
        "can_reach_server": system_health.async_check_can_reach_url(
            hass, Airly.AIRLY_API_URL
        ),
        "requests_remaining": requests_remaining,
        "requests_per_day": requests_per_day,
    }
