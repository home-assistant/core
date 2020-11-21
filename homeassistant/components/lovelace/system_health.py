"""Provide info to system health."""
from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info, "/config/lovelace")


async def system_health_info(hass):
    """Get info for the info page."""
    health_info = {"dashboards": len(hass.data[DOMAIN]["dashboards"])}
    health_info.update(await hass.data[DOMAIN]["dashboards"][None].async_get_info())
    health_info.update(await hass.data[DOMAIN]["resources"].async_get_info())
    return health_info
