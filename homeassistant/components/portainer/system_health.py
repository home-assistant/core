"""Provide info to system health."""

from typing import Any

from homeassistant.components import system_health
from homeassistant.const import CONF_URL
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
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    return {
        "can_reach_server": system_health.async_check_can_reach_url(
            hass, f"{config_entry.data[CONF_URL].rstrip('/')}/api/system/status"
        ),
    }
