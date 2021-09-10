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
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, HTTP, SIGNAL_CONFIG_OPTIONS_UPDATE, TIMEOUT_SCALE
from .exceptions import CannotConnect, PoweredOff

PLATFORMS = [MEDIA_PLAYER_PLATFORM]

_LOGGER = logging.getLogger(__name__)


async def validate_projector(
    hass: HomeAssistant,
    host,
    timeout_scale=1.0,
    check_power=True,
    check_powered_on=True,
):
    """Validate the given projector host allows us to connect."""
    epson_proj = Projector(
        host=host,
        websession=async_get_clientsession(hass, verify_ssl=False),
        type=HTTP,
        timeout_scale=timeout_scale,
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up epson from a config entry."""
    projector = await validate_projector(
        hass=hass,
        host=entry.data[CONF_HOST],
        timeout_scale=entry.options.get(TIMEOUT_SCALE, 1.0),
        check_power=False,
        check_powered_on=False,
    )
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = projector
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def update_listener(hass, entry):
    """Handle options update."""
    async_dispatcher_send(
        hass, SIGNAL_CONFIG_OPTIONS_UPDATE.format(entry.entry_id), entry.options
    )
