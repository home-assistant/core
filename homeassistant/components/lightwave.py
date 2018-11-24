"""
homeassistant.components.lightwave.

Implements communication with LightwaveRF.

My understanding of the LightWave Hub is that devices cannot be discovered
so must be registered manually. This is done in the configuration file.

lightwave:
    host: ip_address

Where ip_address is the ip address of your LightwaveRF hub

For more details on the api see: https://api.lightwaverf.com/
"""
import voluptuous as vol

from lightwave.lightwave import LWLink
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

DEPENDENCIES = ['lightwave']
LIGHTWAVE_LINK = 'lightwave_link'
DOMAIN = 'lightwave'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Try to start embedded Lightwave broker."""
    host = config[DOMAIN].get(CONF_HOST)
    hass.data[LIGHTWAVE_LINK] = LWLink(host)
    return True
