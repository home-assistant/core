"""The Uptime Robot integration."""
from __future__ import annotations

import async_timeout
from pyuptimerobot import UptimeRobot

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_ATTR_MONITORS,
    API_ATTR_OK,
    API_ATTR_STAT,
    CONNECTION_ERROR,
    COORDINATOR_UPDATE_INTERVAL,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    MonitorData,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Uptime Robot from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    uptime_robot_api = UptimeRobot()

    async def async_update_data() -> list[MonitorData]:
        """Fetch data from API UptimeRobot API."""
        async with async_timeout.timeout(10):
            monitors = await hass.async_add_executor_job(
                uptime_robot_api.getMonitors, entry.data[CONF_API_KEY]
            )
            if not monitors or monitors.get(API_ATTR_STAT) != API_ATTR_OK:
                raise UpdateFailed(CONNECTION_ERROR)
            return [
                MonitorData.from_dict(monitor)
                for monitor in monitors.get(API_ATTR_MONITORS, [])
            ]

    hass.data[DOMAIN][entry.entry_id] = coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=COORDINATOR_UPDATE_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
