"""The Uptime Robot integration."""
from __future__ import annotations

from pyuptimerobot import (
    UptimeRobot,
    UptimeRobotAuthenticationException,
    UptimeRobotException,
    UptimeRobotMonitor,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_ATTR_OK, COORDINATOR_UPDATE_INTERVAL, DOMAIN, LOGGER, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Uptime Robot from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    uptime_robot_api = UptimeRobot(
        entry.data[CONF_API_KEY], async_get_clientsession(hass)
    )

    async def async_update_data() -> list[UptimeRobotMonitor]:
        """Fetch data from API UptimeRobot API."""
        try:
            response = await uptime_robot_api.async_get_monitors()
        except UptimeRobotAuthenticationException as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except UptimeRobotException as exception:
            raise UpdateFailed(exception) from exception
        else:
            if response.status == API_ATTR_OK:
                monitors: list[UptimeRobotMonitor] = response.data
                return monitors
            raise UpdateFailed(response.error.message)

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
