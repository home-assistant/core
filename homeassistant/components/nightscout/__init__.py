"""The Nightscout integration."""
from asyncio import TimeoutError as AsyncIOTimeoutError

from aiohttp import ClientError
from py_nightscout import Api as NightscoutAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import SLOW_UPDATE_WARNING

from .const import DOMAIN

PLATFORMS = ["sensor"]
_API_TIMEOUT = SLOW_UPDATE_WARNING - 1


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Nightscout from a config entry."""
    server_url = entry.data[CONF_URL]
    api_key = entry.data.get(CONF_API_KEY)
    session = async_get_clientsession(hass)
    api = NightscoutAPI(server_url, session=session, api_secret=api_key)
    try:
        status = await api.get_server_status()
    except (ClientError, AsyncIOTimeoutError, OSError) as error:
        raise ConfigEntryNotReady from error

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, server_url)},
        manufacturer="Nightscout Foundation",
        name=status.name,
        sw_version=status.version,
        entry_type="service",
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
