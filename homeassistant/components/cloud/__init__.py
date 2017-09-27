"""Component to integrate the Home Assistant cloud."""
import asyncio
import logging

import voluptuous as vol

from . import http_api, auth_api
from .const import DOMAIN


REQUIREMENTS = ['warrant==0.2.0']
DEPENDENCIES = ['http']
CONF_MODE = 'mode'
MODE_DEV = 'development'
MODE_STAGING = 'staging'
MODE_PRODUCTION = 'production'
DEFAULT_MODE = MODE_DEV

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_MODE, default=DEFAULT_MODE):
        vol.In([MODE_DEV, MODE_STAGING, MODE_PRODUCTION]),
    }),
}, extra=vol.ALLOW_EXTRA)
_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the Home Assistant cloud."""
    mode = MODE_PRODUCTION

    if DOMAIN in config:
        mode = config[DOMAIN].get(CONF_MODE)

    if mode != 'development':
        _LOGGER.error('Only development mode is currently allowed.')
        return False

    data = hass.data[DOMAIN] = {
        'mode': mode
    }

    data['auth'] = yield from hass.async_add_job(auth_api.load_auth, hass)

    yield from http_api.async_setup(hass)
    return True
