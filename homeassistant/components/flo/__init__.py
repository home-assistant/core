"""The flo integration."""
import asyncio
import logging

from aioflo import async_get_api
from aioflo.errors import RequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLIENT, DOMAIN
from .device import FloDeviceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up flo from a config entry."""
    session = async_get_clientsession(hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}
    try:
        hass.data[DOMAIN][entry.entry_id][CLIENT] = client = await async_get_api(
            entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session=session
        )
    except RequestError as err:
        raise ConfigEntryNotReady from err

    user_info = await client.user.get_info(include_location_info=True)

    _LOGGER.debug("Flo user information with locations: %s", user_info)

    hass.data[DOMAIN][entry.entry_id]["devices"] = devices = [
        FloDeviceDataUpdateCoordinator(hass, client, location["id"], device["id"])
        for location in user_info["locations"]
        for device in location["devices"]
    ]

    tasks = [device.async_refresh() for device in devices]
    await asyncio.gather(*tasks)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
