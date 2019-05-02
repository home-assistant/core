"""Support for an Intergas boiler via an InComfort/Intouch Lan2RF gateway."""
import logging

import voluptuous as vol
from incomfortclient import Gateway as InComfortGateway

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'incomfort'

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
    """Create an Intergas InComfort/Intouch system."""
    incomfort_data = hass.data[DOMAIN] = {}

    credentials = dict(hass_config[DOMAIN])
    hostname = credentials.pop(CONF_HOST)

    try:
        client = incomfort_data['client'] = InComfortGateway(
            hostname, **credentials, session=async_get_clientsession(hass)
        )

        heater = incomfort_data['heater'] = list(await client.heaters)[0]
        await heater.update()

    except AssertionError:  # assert response.status == HTTP_OK
        _LOGGER.warning(
            "setup(): Failed, check your configuration.",
            exc_info=True)
        return False

    hass.async_create_task(async_load_platform(
        hass, 'water_heater', DOMAIN, {}, hass_config))

    hass.async_create_task(async_load_platform(
        hass, 'binary_sensor', DOMAIN, {}, hass_config))

    hass.async_create_task(async_load_platform(
        hass, 'sensor', DOMAIN, {}, hass_config))

    if len(heater.rooms) > -1:
        hass.async_create_task(async_load_platform(
            hass, 'climate', DOMAIN, {}, hass_config))

    return True
