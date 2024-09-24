"""The awair component."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import (
    AwairCloudDataUpdateCoordinator,
    AwairDataUpdateCoordinator,
    AwairLocalDataUpdateCoordinator,
)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Awair integration from a config entry."""
    session = async_get_clientsession(hass)

    coordinator: AwairDataUpdateCoordinator

    if CONF_HOST in config_entry.data:
        coordinator = AwairLocalDataUpdateCoordinator(hass, config_entry, session)
        config_entry.async_on_unload(
            config_entry.add_update_listener(_async_update_listener)
        )
    else:
        coordinator = AwairCloudDataUpdateCoordinator(hass, config_entry, session)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    coordinator: AwairLocalDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if entry.title != coordinator.title:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Awair configuration."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
