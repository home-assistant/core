"""
Support for Plum Lightpad switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/plum_lightpad
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['plumlightpad==0.0.9']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'plum_lightpad'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

PLUM_DATA = 'plum'


def setup(hass, config):
    """Setup the Plum Lightpad component."""
    from plumlightpad import Plum

    conf = config[DOMAIN]
    plum = Plum(conf[CONF_USERNAME], conf[CONF_PASSWORD])

    hass.data[PLUM_DATA] = plum

    @callback
    def cleanup(event):
        """Clean up resources."""
        plum.cleanup()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)

    discovery.load_platform(hass, 'light', DOMAIN, None, conf)
    discovery.load_platform(hass, 'sensor', DOMAIN, None, conf)
    discovery.load_platform(hass, 'binary_sensor', DOMAIN, None, conf)

    hass.add_job(plum.discover(hass.loop))

    return True
