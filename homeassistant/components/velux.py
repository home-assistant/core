"""
Connects to VELUX KLF 200 interface.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/velux/
"""
import logging

import voluptuous as vol

from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_HOST, CONF_PASSWORD)

DOMAIN = "velux"
DATA_VELUX = "data_velux"
SUPPORTED_DOMAINS = ['scene']
_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyvlx==0.1.3']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the velux component."""
    from pyvlx import PyVLXException
    try:
        hass.data[DATA_VELUX] = VeluxModule(hass, config)
        await hass.data[DATA_VELUX].async_start()

    except PyVLXException as ex:
        _LOGGER.exception("Can't connect to velux interface: %s", ex)
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
        host = config[DOMAIN].get(CONF_HOST)
        password = config[DOMAIN].get(CONF_PASSWORD)
        self.pyvlx = PyVLX(
            host=host,
            password=password)

    async def async_start(self):
        """Start velux component."""
        await self.pyvlx.load_scenes()
