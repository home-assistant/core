"""The Balboa Spa Client integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from pybalboa import SpaClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util

from .const import CONF_SYNC_TIME, DEFAULT_SYNC_TIME, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.LIGHT,
    Platform.SELECT,
]


KEEP_ALIVE_INTERVAL = timedelta(minutes=1)
SYNC_TIME_INTERVAL = timedelta(hours=1)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Balboa Spa from a config entry."""
    host = entry.data[CONF_HOST]

    _LOGGER.debug("Attempting to connect to %s", host)
    spa = SpaClient(host)
    if not await spa.connect():
        _LOGGER.error("Failed to connect to spa at %s", host)
        raise ConfigEntryNotReady("Unable to connect")
    if not await spa.async_configuration_loaded():
        _LOGGER.error("Failed to get spa info at %s", host)
        raise ConfigEntryNotReady("Unable to configure")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = spa

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await async_setup_time_sync(hass, entry)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Disconnecting from spa")
    spa: SpaClient = hass.data[DOMAIN][entry.entry_id]

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    await spa.disconnect()

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_time_sync(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up the time sync."""
    if not entry.options.get(CONF_SYNC_TIME, DEFAULT_SYNC_TIME):
        return

    _LOGGER.debug("Setting up daily time sync")
    spa: SpaClient = hass.data[DOMAIN][entry.entry_id]

    async def sync_time(now: datetime) -> None:
        now = dt_util.as_local(now)
        if (now.hour, now.minute) != (spa.time_hour, spa.time_minute):
            _LOGGER.debug("Syncing time with Home Assistant")
            await spa.set_time(now.hour, now.minute)

    await sync_time(dt_util.utcnow())
    entry.async_on_unload(
        async_track_time_interval(hass, sync_time, SYNC_TIME_INTERVAL)
    )
