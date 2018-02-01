"""
Support for CM15A/CM19A X10 Controller using mochad daemon.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mochad/
"""
import logging
import threading

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.const import (CONF_HOST, CONF_PORT)

REQUIREMENTS = ['pymochad==0.1.1']

_LOGGER = logging.getLogger(__name__)

CONTROLLER = None

CONF_COMM_TYPE = 'comm_type'

DOMAIN = 'mochad'

REQ_LOCK = threading.Lock()

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST, default='localhost'): cv.string,
        vol.Optional(CONF_PORT, default=1099): cv.port,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the mochad component."""
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)

    from pymochad import exceptions

    global CONTROLLER
    try:
        CONTROLLER = MochadCtrl(host, port)
    except exceptions.ConfigurationError:
        _LOGGER.exception()
        return False

    def stop_mochad(event):
        """Stop the Mochad service."""
        CONTROLLER.disconnect()

    def start_mochad(event):
        """Start the Mochad service."""
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_mochad)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_mochad)

    return True


class MochadCtrl(object):
    """Mochad controller."""

    def __init__(self, host, port):
        """Initialize a PyMochad controller."""
        super(MochadCtrl, self).__init__()
        self._host = host
        self._port = port

        from pymochad import controller

        self.ctrl = controller.PyMochad(server=self._host, port=self._port)

    @property
    def host(self):
        """Return the server where mochad is running."""
        return self._host

    @property
    def port(self):
        """Return the port mochad is running on."""
        return self._port

    def disconnect(self):
        """Close the connection to the mochad socket."""
        self.ctrl.socket.close()
