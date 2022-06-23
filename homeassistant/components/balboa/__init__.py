"""The Balboa Spa Client integration."""
import asyncio
from datetime import datetime, timedelta
import time

from pybalboa import BalboaSpaWifi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util

from .const import (
    _LOGGER,
    CONF_SYNC_TIME,
    DEFAULT_SYNC_TIME,
    DOMAIN,
    PLATFORMS,
    SIGNAL_UPDATE,
)

KEEP_ALIVE_INTERVAL = timedelta(minutes=1)
SYNC_TIME_INTERVAL = timedelta(days=1)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Balboa Spa from a config entry."""
    host = entry.data[CONF_HOST]

    _LOGGER.debug("Attempting to connect to %s", host)
    spa = BalboaSpaWifi(host)
    connected = await spa.connect()
    if not connected:
        _LOGGER.error("Failed to connect to spa at %s", host)
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = spa

    async def _async_balboa_update_cb() -> None:
        """Primary update callback called from pybalboa."""
        _LOGGER.debug("Primary update callback triggered")
        async_dispatcher_send(hass, SIGNAL_UPDATE.format(entry.entry_id))

    # set the callback so we know we have new data
    spa.new_data_cb = _async_balboa_update_cb

    _LOGGER.debug("Starting listener and monitor tasks")
    monitoring_tasks = [asyncio.create_task(spa.listen())]
    await spa.spa_configured()
    monitoring_tasks.append(asyncio.create_task(spa.check_connection_status()))

    def stop_monitoring() -> None:
        """Stop monitoring the spa connection."""
        _LOGGER.debug("Canceling listener and monitor tasks")
        for task in monitoring_tasks:
            task.cancel()

    entry.async_on_unload(stop_monitoring)

    # At this point we have a configured spa.
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def keep_alive(now: datetime) -> None:
        """Keep alive task."""
        _LOGGER.debug("Keep alive")
        await spa.send_mod_ident_req()

    entry.async_on_unload(
        async_track_time_interval(hass, keep_alive, KEEP_ALIVE_INTERVAL)
    )

    # call update_listener on startup and for options change as well.
    await async_setup_time_sync(hass, entry)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Disconnecting from spa")
    spa: BalboaSpaWifi = hass.data[DOMAIN][entry.entry_id]

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
    spa: BalboaSpaWifi = hass.data[DOMAIN][entry.entry_id]

    async def sync_time(now: datetime) -> None:
        _LOGGER.debug("Syncing time with Home Assistant")
        await spa.set_time(time.strptime(str(dt_util.now()), "%Y-%m-%d %H:%M:%S.%f%z"))

    await sync_time(dt_util.utcnow())
    entry.async_on_unload(
        async_track_time_interval(hass, sync_time, SYNC_TIME_INTERVAL)
    )
