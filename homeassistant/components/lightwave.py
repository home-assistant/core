"""
Support for device connected via Lightwave WiFi-link hub.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lightwave/
"""
import voluptuous as vol
from homeassistant.const import (CONF_HOST, CONF_LIGHTS, CONF_NAME,
                                 CONF_SWITCHES)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

REQUIREMENTS = ['lightwave==0.15']
LIGHTWAVE_LINK = 'lightwave_link'
DOMAIN = 'lightwave'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_LIGHTS, default={}): {
            cv.string: vol.Schema({vol.Required(CONF_NAME): cv.string}),
        },
        vol.Optional(CONF_SWITCHES, default={}): {
            cv.string: vol.Schema({vol.Required(CONF_NAME): cv.string}),
        }
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Try to start embedded Lightwave broker."""
    lights = config[DOMAIN][CONF_LIGHTS]
    switches = config[DOMAIN][CONF_SWITCHES]

    if not lights and not switches:
        return True

    from lightwave.lightwave import LWLink

    host = config[DOMAIN][CONF_HOST]
    hass.data[LIGHTWAVE_LINK] = LWLink(host)

    if lights:
        hass.async_create_task(async_load_platform(
            hass, 'light', DOMAIN, lights, config))

    if switches:
        hass.async_create_task(async_load_platform(
            hass, 'switch', DOMAIN, switches, config))

    return True
