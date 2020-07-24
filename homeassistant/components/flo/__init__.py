"""The flo integration."""
import asyncio
import logging

from aioflo import async_get_api
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .device import FloDevice

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the flo component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up flo from a config entry."""
    hass.data[DOMAIN][entry.entry_id] = {}
    session = async_get_clientsession(hass)
    hass.data[DOMAIN][entry.entry_id]["client"] = client = await async_get_api(
        entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session=session
    )
    user_info = await client.user.get_info(include_location_info=True)

    _LOGGER.debug("Flo user information with locations: %s", user_info)

    tasks = [
        client.device.get_info(device["id"])
        for location in user_info["locations"]
        for device in location["devices"]
    ]

    results = await asyncio.gather(*tasks)

    hass.data[DOMAIN]["devices"] = devices = [
        FloDevice(hass, result, client) for result in results
    ]

    tasks = [device.update_consumption_data() for device in devices]
    await asyncio.gather(*tasks)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    for device in hass.data[DOMAIN]["devices"]:
        for unsub in device.unsubs:
            unsub()

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
