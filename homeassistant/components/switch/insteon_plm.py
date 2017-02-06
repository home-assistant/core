"""
Support for INSTEON dimmers via PowerLinc Modem.
"""
import logging
import asyncio

from homeassistant.components.switch import SwitchDevice
from homeassistant.loader import get_component
import homeassistant.util as util

DEPENDENCIES = ['insteon_plm']

_LOGGER = logging.getLogger(__name__)

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Moo."""
    _LOGGER.info('Provisioning Insteon PLM Switches')


class InsteonPLMDimmerDevice(Light):
    """Moo."""
    def __init__
