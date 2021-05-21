"""The epson integration."""
import logging

from epson_projector import Projector
from epson_projector.const import (
    PWR_OFF_STATE,
    STATE_UNAVAILABLE as EPSON_STATE_UNAVAILABLE,
)

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_PLATFORM
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, HTTP
from .exceptions import CannotConnect, PoweredOff

PLATFORMS = [MEDIA_PLAYER_PLATFORM]

_LOGGER = logging.getLogger(__name__)


async def validate_projector(
    hass: HomeAssistant, host, check_power=True, check_powered_on=True
):
    """Validate the given projector host allows us to connect."""
    epson_proj = Projector(
        host=host,
        websession=async_get_clientsession(hass, verify_ssl=False),
        type=HTTP,
    )
    if check_power:
        _power = await epson_proj.get_power()
        if not _power or _power == EPSON_STATE_UNAVAILABLE:
            _LOGGER.debug("Cannot connect to projector")
            raise CannotConnect
        if _power == PWR_OFF_STATE and check_powered_on:
            _LOGGER.debug("Projector is off")
            raise PoweredOff
    return epson_proj


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up epson from a config entry."""
    projector = await validate_projector(
        hass=hass,
        host=entry.data[CONF_HOST],
        check_power=False,
        check_powered_on=False,
    )
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = projector
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
