"""The UptimeRobot integration."""

from __future__ import annotations

from pyuptimerobot import UptimeRobot

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS
from .coordinator import UptimeRobotDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up UptimeRobot from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    key: str = entry.data[CONF_API_KEY]
    if key.startswith(("ur", "m")):
        raise ConfigEntryAuthFailed(
            "Wrong API key type detected, use the 'main' API key"
        )
    uptime_robot_api = UptimeRobot(key, async_get_clientsession(hass))
    dev_reg = dr.async_get(hass)

    hass.data[DOMAIN][entry.entry_id] = coordinator = UptimeRobotDataUpdateCoordinator(
        hass,
        config_entry_id=entry.entry_id,
        dev_reg=dev_reg,
        api=uptime_robot_api,
    )

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
