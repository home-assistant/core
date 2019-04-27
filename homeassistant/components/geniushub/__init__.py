"""This module connects to a Genius hub and shares the data."""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'geniushub'

_V1_API_SCHEMA = vol.Schema({
    vol.Required(CONF_TOKEN): cv.string,
})
_V3_API_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Any(
        _V3_API_SCHEMA,
        _V1_API_SCHEMA,
    )
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, hass_config):
    """Create a Genius Hub system."""
    from geniushubclient import GeniusHubClient  # noqa; pylint: disable=no-name-in-module

    geniushub_data = hass.data[DOMAIN] = {}

    kwargs = dict(hass_config[DOMAIN])
    if CONF_HOST in kwargs:
        args = (kwargs.pop(CONF_HOST), )
    else:
        args = (kwargs.pop(CONF_TOKEN), )

    try:
        client = geniushub_data['client'] = GeniusHubClient(
            *args, **kwargs, session=async_get_clientsession(hass)
        )

        await client.hub.update()

    except AssertionError:  # assert response.status == HTTP_OK
        _LOGGER.warning(
            "setup(): Failed, check your configuration.",
            exc_info=True)
        return False

    hass.async_create_task(async_load_platform(
        hass, 'climate', DOMAIN, {}, hass_config))

    return True
