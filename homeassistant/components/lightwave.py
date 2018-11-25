"""
Support for device connected via Lightwave WiFi-link hub.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lightwave/
"""
import voluptuous as vol

from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

REQUIREMENTS = ['lightwave==0.14']
LIGHTWAVE_LINK = 'lightwave_link'
DOMAIN = 'lightwave'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Try to start embedded Lightwave broker."""
    from lightwave.lightwave import LWLink

    host = config[DOMAIN][CONF_HOST]
    hass.data[LIGHTWAVE_LINK] = LWLink(host)
    return True
