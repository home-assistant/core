"""The epson integration."""
import asyncio
import logging

from epson_projector import Projector
from epson_projector.const import POWER, STATE_UNAVAILABLE as EPSON_STATE_UNAVAILABLE

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_PLATFORM
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .exceptions import CannotConnect

PLATFORMS = [MEDIA_PLAYER_PLATFORM]

_LOGGER = logging.getLogger(__name__)


async def validate_projector(hass: HomeAssistant, host, port):
    """Validate the given host and port allows us to connect."""
    epson_proj = Projector(
        host=host,
        websession=async_get_clientsession(hass, verify_ssl=False),
        port=port,
    )
    _power = await epson_proj.get_property(POWER)
    if not _power or _power == EPSON_STATE_UNAVAILABLE:
        raise CannotConnect
    return epson_proj


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the epson component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up epson from a config entry."""
    try:
        projector = await validate_projector(
            hass, entry.data[CONF_HOST], entry.data[CONF_PORT]
        )
    except CannotConnect:
        _LOGGER.warning("Cannot connect to projector %s", entry.data[CONF_HOST])
        return False
    hass.data[DOMAIN][entry.entry_id] = projector
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
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
