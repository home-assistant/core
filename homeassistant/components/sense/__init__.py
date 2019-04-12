"""Support for monitoring a Sense energy sensor."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TIMEOUT
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

REQUIREMENTS = ['sense_energy==0.7.0']

_LOGGER = logging.getLogger(__name__)

ACTIVE_UPDATE_RATE = 60

DEFAULT_TIMEOUT = 5
DOMAIN = 'sense'

SENSE_DATA = 'sense_data'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Sense sensor."""
    from sense_energy import ASyncSenseable, SenseAuthenticationException

    username = config[DOMAIN][CONF_EMAIL]
    password = config[DOMAIN][CONF_PASSWORD]

    timeout = config[DOMAIN][CONF_TIMEOUT]
    try:
        hass.data[SENSE_DATA] = ASyncSenseable(
            api_timeout=timeout, wss_timeout=timeout)
        hass.data[SENSE_DATA].rate_limit = ACTIVE_UPDATE_RATE
        await hass.data[SENSE_DATA].authenticate(username, password)
    except SenseAuthenticationException:
        _LOGGER.error("Could not authenticate with sense server")
        return False
    hass.async_create_task(
        async_load_platform(hass, 'sensor', DOMAIN, {}, config))
    hass.async_create_task(
        async_load_platform(hass, 'binary_sensor', DOMAIN, {}, config))
    return True
