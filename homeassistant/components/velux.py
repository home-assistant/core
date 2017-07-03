"""
Connects to VELUX KLF 200 interface.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.velux/

"""

import logging
import asyncio

import voluptuous as vol

from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_HOST, CONF_PASSWORD)

DOMAIN = "velux"
SUPPORTED_DOMAINS = ['scene']
_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyvlx==0.1.2']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the velux component."""
    from pyvlx import PyVLXException
    try:
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = VeluxModule(hass, config)
            yield from hass.data[DOMAIN].async_start()

    except PyVLXException as ex:
        _LOGGER.exception("Can't connect to velux interface: %s", ex)
        hass.data[DOMAIN] = None
        return False

    for component in SUPPORTED_DOMAINS:
        hass.async_add_job(
            discovery.async_load_platform(hass, component, DOMAIN, {}, config))
    return True


class VeluxModule:
    """Abstraction for velux component."""

    def __init__(self, hass, config):
        """Initialize for velux component."""
        from pyvlx import PyVLX
        self.initialized = False
        host = config[DOMAIN].get(CONF_HOST)
        password = config[DOMAIN].get(CONF_PASSWORD)
        self.pyvlx = PyVLX(
            host=host,
            password=password)
        self.initialized = False
        self.hass = hass

    @asyncio.coroutine
    def async_start(self):
        """Start velux component."""
        yield from self.pyvlx.load_scenes()
        self.initialized = True
