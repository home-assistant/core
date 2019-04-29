"""This integration connects to an Intergas Intouch Lan2RF gateway."""
import logging

import voluptuous as vol
from intouchclient import InComfortClient

from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'intouch'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All({
        vol.Required(CONF_HOST): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, hass_config):
    """Create a Intergas Intouch system."""

    intouch_data = hass.data[DOMAIN] = {}

    hostname = hass_config[DOMAIN][CONF_HOST]

    try:
        client = intouch_data['client'] = InComfortClient(
            hostname, session=async_get_clientsession(hass)
        )

        await client.gateway.update()

    except AssertionError:  # assert response.status == HTTP_OK
        _LOGGER.warning(
            "setup(): Failed, check your configuration.",
            exc_info=True)
        return False

    hass.async_create_task(async_load_platform(
        hass, 'climate', DOMAIN, {}, hass_config))

    return True
