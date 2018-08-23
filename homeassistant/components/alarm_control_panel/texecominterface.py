"""
Support for texecom panel interface

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/texecom/
"""

import asyncio
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.texecom import (
    DATA_EVL, CONF_PORT, TexecomPanelInterface)


from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['texecom']

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Serial Panel Interface Platform."""
    port = discovery_info['port']
    name = 'TexecomPanelInterface'

    panelinterface = TexecomPanelInterface(name, port)

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, panelinterface.stop_serial_read())

    async_add_devices([panelinterface], True)

