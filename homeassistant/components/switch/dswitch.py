"""
Support for dSwitch - switch over WiFi

"""
import logging
import socket
import asyncio
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    CONF_NAME, CONF_ID, CONF_IP_ADDRESS, CONF_PORT)

_LOGGER = logging.getLogger(__name__)

ON_MESSAGE = "{c:ton}"
OFF_MESSAGE = "{c:tof}"

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the dSwitch switch platform."""
    name = config.get(CONF_NAME)
    id = config.get(CONF_ID)
    ip_address = config.get(CONF_IP_ADDRESS)
    port = config.get(CONF_PORT)
    async_add_devices([dSwitch(id, name, ip_address, port)])

class dSwitch(SwitchDevice):
    """Representation of an dSwitch switch device."""

    def __init__(self, id, name, ip_address, port):
        """Initialize the HomeBound switch device."""
        self._on_state = False
        self._id = id
        self._name = name
        self._ip_address = ip_address
        self._port = port

    @property
    def is_on(self):
        """Return whether the switch is on or off."""
        return self._on_state

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._id

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        self._on_state = True
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((self._ip_address, self._port))
            s.send(ON_MESSAGE)
        except socket.error as ex:
            _LOGGER.error("Error occured: %(err)s",
                      dict(err=str(ex)))
        finally:
            s.close()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        self._on_state = False
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((self._ip_address, self._port))
            s.send(OFF_MESSAGE)
        except socket.error as ex:
            _LOGGER.error("Error occured: %(err)s",
                      dict(err=str(ex)))
        finally:
            s.close()