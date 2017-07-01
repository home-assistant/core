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
VELUX_MODULE = None

REQUIREMENTS = ['pyvlx==0.1.1']


@asyncio.coroutine
def async_setup(hass, config):
    """Setup device tracker."""

    # pylint: disable=global-statement, import-error
    global VELUX_MODULE

    if VELUX_MODULE is None:
        VELUX_MODULE = VeluxModule(hass, config)
        yield from VELUX_MODULE.async_start()

    for component in SUPPORTED_DOMAINS:
        hass.async_add_job(
            discovery.async_load_platform(hass, component, DOMAIN, {}, config))
    return True


class VeluxModule:
    """Abstraction for Velux Compoent"""
    def __init__(self, hass, config):
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
        """ Start VELUX compoent """
        yield from self.pyvlx.load_scenes()
        self.initialized = True


class VeluxConfig:
    """Representation of Configuration Velux Config"""
    def __init__(self, hass, config):
        """ Init VELUX Configuration """
        self.hass = hass
        self.config = config
        self.velux_config = config.get(DOMAIN, {})
        self.host = self.get_config_value("host")
        self.password = self.get_config_value("password")

    def get_config_value(self, key, default_value=None):
        """ Get configuration value from VELUX Config """
        if key not in self.velux_config:
            return default_value
        return self.velux_config[key]
