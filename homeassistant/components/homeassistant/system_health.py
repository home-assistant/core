"""Provide info to system health."""
from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import system_info


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass):
    """Get info for the info page."""
    info = await system_info.async_get_system_info(hass)

    # Moved to homeassistant/components/hassio/system_health.py
    for key in ["hassio", "supervisor", "host_os", "chassis", "docker_version"]:
        if key in info:
            info.pop(key)

    return info
