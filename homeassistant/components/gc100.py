"""
Support for controlling Global Cache gc100.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/gc100/
"""

import logging
import sys

from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP, CONF_HOST, CONF_PORT)

REQUIREMENTS = ['python-gc100==1.0.1a']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'gc100'

DATA_GC100 = 'gc100'


# pylint: disable=no-member
# pylint: disable=import-self
def setup(hass, base_config):
    """Set up the gc100 component."""
    import gc100

    config = base_config[DOMAIN]
    host = config[CONF_HOST]
    port = config[CONF_PORT]

    gc_device = gc100.GC100SocketClient(host, port)

    def cleanup_gc100():
        """Stuff to do before stopping."""
        gc_device.quit()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gc100)

    hass.data[DATA_GC100] = GC100Device(hass, gc_device)

    return True


class GC100Device(object):
    """The GC100 component."""

    def __init__(self, hass, gc_device):
        """Init gc100 device."""
        self.hass = hass
        self.gc_device = gc_device

    def read_sensor(self, port_addr, callback):
        """Read a value from a digital input."""
        self.gc_device.read_sensor(port_addr, callback)

    def write_switch(self, port_addr, state, callback):
        """Write a value to a relay."""
        self.gc_device.write_switch(port_addr, state, callback)

    def subscribe(self, port_addr, callback):
        """Add detection for RISING and FALLING events."""
        self.gc_device.subscribe_notify(port_addr, callback)
