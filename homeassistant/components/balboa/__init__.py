"""The Balboa Spa Client integration."""
import asyncio
import time

from pybalboa import BalboaSpaWifi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util

from .const import _LOGGER, CONF_SYNC_TIME, DEFAULT_SYNC_TIME, DOMAIN, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Balboa Spa from a config entry."""
    host = entry.data[CONF_HOST]

    _LOGGER.debug("Attempting to connect to %s", host)
    spa = BalboaSpaWifi(host)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = spa

    connected = await spa.connect()
    if not connected:
        _LOGGER.error("Failed to connect to spa at %s", host)
        raise ConfigEntryNotReady

    # send config requests, and then listen until we are configured.
    await spa.send_mod_ident_req()
    await spa.send_panel_req(0, 1)

    _LOGGER.debug("Starting listener and monitor tasks")
    hass.loop.create_task(spa.listen())
    await spa.spa_configured()
    asyncio.create_task(spa.check_connection_status())

    # At this point we have a configured spa.
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def _async_balboa_update_cb():
        """Primary update callback called from pybalboa."""
        _LOGGER.debug("Primary update callback triggered")
        async_dispatcher_send(hass, DOMAIN)

    spa.new_data_cb = _async_balboa_update_cb

    # call update_listener on startup
    await update_listener(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    _LOGGER.debug("Disconnecting from spa")
    spa = hass.data[DOMAIN][entry.entry_id]
    await spa.disconnect()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass, entry):
    """Handle options update."""
    if not entry.options.get(CONF_SYNC_TIME, DEFAULT_SYNC_TIME):
        return

    _LOGGER.debug("Setting up daily time sync")
    spa = hass.data[DOMAIN][entry.entry_id]

    async def sync_time():
        if entry.options.get(CONF_SYNC_TIME, DEFAULT_SYNC_TIME):
            _LOGGER.debug("Syncing time with Home Assistant")
            await spa.set_time(
                time.strptime(str(dt_util.now()), "%Y-%m-%d %H:%M:%S.%f%z")
            )

    sync_time()
    entry.async_on_unload(async_track_time_interval(hass, sync_time, 86400))
