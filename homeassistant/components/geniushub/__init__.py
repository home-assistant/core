''' This module connects to the Genius hub and shares the data'''
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_SCAN_INTERVAL)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

REQUIREMENTS = ['geniushub==0.1']
GENIUS_HUB = 'genius_hub'
DOMAIN = 'geniushub'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=6): cv.positive_int,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    from geniushub.geniushub import GeniusHub
    """Try to start embedded Genius Hub  broker."""
    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    host = config[DOMAIN].get(CONF_HOST)
    scan_interval = config[DOMAIN].get(CONF_SCAN_INTERVAL)
    hass.data[GENIUS_HUB] = GeniusHub(
        host, username, password, scan_interval)

    hass.async_create_task(async_load_platform(
        hass, 'climate', DOMAIN, None, config))

    hass.async_create_task(async_load_platform(
        hass, 'switch', DOMAIN, None, config))

    hass.async_create_task(async_load_platform(
        hass, 'sensor', DOMAIN, None, config))

    return True
