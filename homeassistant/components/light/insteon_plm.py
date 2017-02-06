"""
Support for INSTEON dimmers via PowerLinc Modem.
"""
import logging
import asyncio

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.loader import get_component
import homeassistant.util as util

DEPENDENCIES = ['insteon_plm']

_LOGGER = logging.getLogger(__name__)

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Moo."""
    _LOGGER.info('Provisioning Insteon PLM Lights')

    plm = hass.data['insteon_plm']

    def async_insteonplm_light_callback(device):
        """New device detected from transport."""
        _LOGGER.info('New INSTEON PLM light device: %s', device)

    new_lights = []

    yield from async_add_devices(new_lights)
