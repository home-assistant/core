import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from . import http_api, cloud_api
from .const import DOMAIN


DEPENDENCIES = ['http']
CONF_DEVELOPMENT = 'development'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_DEVELOPMENT, default=False): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)
_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the Home Assistant cloud."""
    if not config[DOMAIN][CONF_DEVELOPMENT]:
        _LOGGER.error('Production mode not available yet.')
        return False

    cloud = yield from cloud_api.async_load_auth(hass, 'development')

    if cloud is not None:
        hass.data[DOMAIN] = cloud

    yield from http_api.async_setup(hass)
    return True
