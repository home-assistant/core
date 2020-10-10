"""Roon (www.roonlabs.com) component."""
import logging

from homeassistant.const import CONF_HOST
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .server import RoonServer

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the Roon platform."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass, entry):
    """Set up a roonserver from a config entry."""
    host = entry.data[CONF_HOST]
    roonserver = RoonServer(hass, entry)

    if not await roonserver.async_setup():
        return False

    hass.data[DOMAIN][entry.entry_id] = roonserver
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Roonlabs",
        name=host,
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    roonserver = hass.data[DOMAIN].pop(entry.entry_id)
    return await roonserver.async_reset()
