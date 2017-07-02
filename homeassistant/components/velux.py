"""

Connects to VELUX KLF 200 interface

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.velux/

"""

import logging
import asyncio
from homeassistant.helpers import discovery

DOMAIN = "velux"
SUPPORTED_DOMAINS = ['scene']
_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyvlx==0.1.1']


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the velux component."""


    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = VeluxModule(hass, config)
        yield from hass.data[DOMAIN].async_start()

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
        velux_config = VeluxConfig(hass, config)
        self.pyvlx = PyVLX(
            host=velux_config.host,
            password=velux_config.password)
        self.initialized = False
        self.hass = hass

    @asyncio.coroutine
    def async_start(self):
        """Start velux component."""
        yield from self.pyvlx.load_scenes()
        self.initialized = True


class VeluxConfig:
    """Representation of configuration celux config"""
    def __init__(self, hass, config):
        """Init velux configuration."""
        self.hass = hass
        self.config = config
        self.velux_config = config.get(DOMAIN, {})
        self.host = self.get_config_value("host")
        self.password = self.get_config_value("password")

    def get_config_value(self, key, default_value=None):
        """Get configuration value from velux config."""
        if key not in self.velux_config:
            return default_value
        return self.velux_config[key]
