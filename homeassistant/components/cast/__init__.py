"""Component to embed Google Cast."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow
from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN, DEFAULT_PORT, CONF_CAST_MEDIA_PLAYER, CONF_IGNORE_CEC)

REQUIREMENTS = ['pychromecast==2.1.0']

CAST_MEDIA_PLAYER_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): vol.All(cv.string),
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_IGNORE_CEC, default=[]): vol.All(cv.ensure_list,
                                                       [cv.string])
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_CAST_MEDIA_PLAYER):
            vol.All(cv.ensure_list, [CAST_MEDIA_PLAYER_SCHEMA]),
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Cast component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = conf or {}

    if conf is not None:
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT}))

    return True


async def async_setup_entry(hass, entry):
    """Set up Cast from a config entry."""
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(
        entry, 'media_player'))
    return True


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    from pychromecast.discovery import discover_chromecasts

    return await hass.async_add_executor_job(discover_chromecasts)


config_entry_flow.register_discovery_flow(
    DOMAIN, 'Google Cast', _async_has_devices,
    config_entries.CONN_CLASS_LOCAL_PUSH)
