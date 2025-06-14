"""The UptimeRobot integration."""

from __future__ import annotations

from pyuptimerobot import UptimeRobot

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS
from .coordinator import UptimeRobotConfigEntry, UptimeRobotDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: UptimeRobotConfigEntry) -> bool:
    """Set up UptimeRobot from a config entry."""
    key: str = entry.data[CONF_API_KEY]
    if key.startswith(("ur", "m")):
        raise ConfigEntryAuthFailed(
            "Wrong API key type detected, use the 'main' API key"
        )
    uptime_robot_api = UptimeRobot(key, async_get_clientsession(hass))

    coordinator = UptimeRobotDataUpdateCoordinator(
        hass,
        entry,
        api=uptime_robot_api,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: UptimeRobotConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
