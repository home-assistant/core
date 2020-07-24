"""
Roon (www.roonlabs.com) component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/roon/
"""
import logging

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import device_registry as dr

# We need an import from .config_flow, without it .config_flow is never loaded.
from .config_flow import configured_hosts
from .const import CONF_CUSTOM_PLAY_ACTION, DATA_CONFIGS, DOMAIN
from .server import RoonServer

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the Roon platform."""
    hass.data[DOMAIN] = {}
    hass.data[DATA_CONFIGS] = {}
    return True


async def async_setup_entry(hass, entry):
    """Set up a roonserver from a config entry."""
    host = entry.data[CONF_HOST]
    config = hass.data[DATA_CONFIGS].get(host)
    if config is None:
        custom_play_action = None
    else:
        custom_play_action = config[CONF_CUSTOM_PLAY_ACTION]
    roonserver = RoonServer(hass, entry, custom_play_action)

    if not await roonserver.async_setup():
        return False

    hass.data[DOMAIN][host] = roonserver
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(CONF_HOST, host)},
        identifiers={(DOMAIN, host)},
        manufacturer="Roonlabs",
        name=host,
        model="",
        sw_version="",
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    roonserver = hass.data[DOMAIN].pop(entry.data[CONF_HOST])
    return await roonserver.async_reset()
