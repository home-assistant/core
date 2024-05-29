"""Provide info to system health."""

from __future__ import annotations

from typing import Any

from pyisy import ISY

from homeassistant.components import system_health
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, ISY_URL_POSTFIX
from .models import IsyData


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""

    health_info = {}
    config_entry_id = next(
        iter(hass.data[DOMAIN])
    )  # Only first ISY is supported for now
    isy_data: IsyData = hass.data[DOMAIN][config_entry_id]
    isy: ISY = isy_data.root

    entry = hass.config_entries.async_get_entry(config_entry_id)
    assert isinstance(entry, ConfigEntry)
    health_info["host_reachable"] = await system_health.async_check_can_reach_url(
        hass, f"{entry.data[CONF_HOST]}{ISY_URL_POSTFIX}"
    )
    health_info["device_connected"] = isy.connected
    health_info["last_heartbeat"] = isy.websocket.last_heartbeat
    health_info["websocket_status"] = isy.websocket.status

    return health_info
