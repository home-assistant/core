"""Component to integrate the Home Assistant cloud."""
import asyncio
import logging

import voluptuous as vol

from . import http_api, cloud_api
from .const import DOMAIN


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

    cloud = yield from cloud_api.async_load_auth(hass)

    if cloud is not None:
        data['cloud'] = cloud

    yield from http_api.async_setup(hass)
    return True
