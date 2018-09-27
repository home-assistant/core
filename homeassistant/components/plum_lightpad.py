"""
Support for Plum Lightpad switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/plum_lightpad
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP)
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
LIGHTPAD_LOCATED = 'plum.lightpad.found'
LOGICAL_LOAD_LOCATED = 'plum.logicalLoad.found'


async def async_setup(hass, config):
    """Setup the Plum Lightpad component."""
    from plumlightpad import Plum

    conf = config[DOMAIN]
    plum = Plum(conf[CONF_USERNAME], conf[CONF_PASSWORD])

    hass.data[PLUM_DATA] = plum

    async def cleanup(event):
        """Clean up resources."""
        await plum.cleanup()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)

    await plum.loadCloudData()

    discovery.load_platform(hass, 'light', DOMAIN, None, conf)
    discovery.load_platform(hass, 'sensor', DOMAIN, None, conf)
    discovery.load_platform(hass, 'binary_sensor', DOMAIN, None, conf)

    async def new_load(event_data):
        """Called when a new LogicalLoad is detected."""
        hass.bus.async_fire(LOGICAL_LOAD_LOCATED, event_data)

    async def new_lightpad(event_data):
        """Called when a new Lightpad is detected."""
        hass.bus.async_fire(LIGHTPAD_LOCATED, event_data)

    hass.async_add_job(plum.discover(hass.loop, new_load, new_lightpad))

    return True
