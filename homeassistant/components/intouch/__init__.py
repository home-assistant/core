"""This integration connects to an Intergas Intouch Lan2RF gateway."""
import logging

import voluptuous as vol
from intouchclient import InTouchGateway

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_START)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'intouch'

_V1_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
})
_V2_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Any(
        _V1_SCHEMA,
        _V2_SCHEMA,
    )
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, hass_config):
    """Create a Intergas Intouch system."""

    intouch_data = hass.data[DOMAIN] = {}

    kwargs = dict(hass_config[DOMAIN])
    hostname = kwargs.pop(CONF_HOST)

    try:
        client = intouch_data['client'] = InTouchGateway(
            hostname, **kwargs, session=async_get_clientsession(hass)
        )

        heaters = await client.heaters
        await heaters[0].update()

    except AssertionError:  # assert response.status == HTTP_OK
        _LOGGER.warning(
            "setup(): Failed, check your configuration.",
            exc_info=True)
        return False

    hass.async_create_task(async_load_platform(
        hass, 'water_heater', DOMAIN, {}, hass_config))

    hass.async_create_task(async_load_platform(
        hass, 'sensor', DOMAIN, {}, hass_config))

    hass.async_create_task(async_load_platform(
        hass, 'binary_sensor', DOMAIN, {}, hass_config))

    if len(heaters[0].rooms) > -1:  # TODO: should be > 0
        hass.async_create_task(async_load_platform(
            hass, 'climate', DOMAIN, {}, hass_config))

    return True
