"""The SiteSage Emonitor integration."""
import asyncio
from datetime import timedelta
import logging

from aioemonitor import Emonitor

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPDATE_RATE = 60

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up SiteSage Emonitor from a config entry."""

    session = aiohttp_client.async_get_clientsession(hass)
    emonitor = Emonitor(entry.data[CONF_HOST], session)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=entry.title,
        update_method=emonitor.async_get_status,
        update_interval=timedelta(seconds=DEFAULT_UPDATE_RATE),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def name_short_mac(short_mac):
    """Name from short mac."""
    return f"Emonitor {short_mac}"
