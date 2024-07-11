"""The twinkly component."""

from aiohttp import ClientError
from ttls.client import Twinkly

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_SW_VERSION, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ATTR_VERSION, DATA_CLIENT, DATA_DEVICE_INFO, DOMAIN

PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entries from config flow."""
    hass.data.setdefault(DOMAIN, {})

    # We setup the client here so if at some point we add any other entity for this device,
    # we will be able to properly share the connection.
    host = entry.data[CONF_HOST]

    hass.data[DOMAIN].setdefault(entry.entry_id, {})

    client = Twinkly(host, async_get_clientsession(hass))

    try:
        device_info = await client.get_details()
        software_version = await client.get_firmware_version()
    except (TimeoutError, ClientError) as exception:
        raise ConfigEntryNotReady from exception

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_DEVICE_INFO: device_info,
        ATTR_SW_VERSION: software_version.get(ATTR_VERSION),
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove a twinkly entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
