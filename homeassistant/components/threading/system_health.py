"""Provide threading info to system health."""
import threading

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(async_system_health_info)


async def async_system_health_info(hass):
    """Get info for the info page."""
    return {thread.ident: thread.name for thread in threading.enumerate()}
