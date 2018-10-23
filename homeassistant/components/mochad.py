"""
Support for CM15A/CM19A X10 Controller using mochad daemon.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mochad/
"""
import logging
import threading
import asyncio
import time
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.const import (CONF_HOST, CONF_PORT)

REQUIREMENTS = ['pymochad==0.2.0']

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


@asyncio.coroutine
def async_setup(hass, config):
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
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_mochad)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_mochad)

    """Start listening thread for Mochad data."""
    CONTROLLER.start()

    return True


class MochadCtrl(threading.Thread):
    """Mochad controller."""

    def __init__(self, host, port):
        """Initialize a PyMochad controller."""
        super(MochadCtrl, self).__init__()
        self._host = host
        self._port = port

        from pymochad import controller

        self.ctrl = controller.PyMochad(server=self._host, port=self._port)
        super(MochadCtrl, self).__init__()

    def run(self):
        """Run loop in a thread."""
        self._ws_listen()

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

    def _ws_listen(self):
        """Read the data in a loop to exhaust receiving buffer of Mochad."""
        _LOGGER.info("Entering Mochad event listening loop")
        try:
            # READ FROM NETWORK LOOP
            retry_count = 0
            while True:
                try:
                    content = self.ctrl.read_data()
                    if content:
                        retry_count = 0
                except Exception as exception_instance:
                    _LOGGER.error(
                        "Failed to read from the socket. {}".format(exception_instance))
                    if retry_count >= 300:
                        raise Exception(
                            "Retry attempts exceeded. Failed to read for the"
                            " socket.")
                    else:
                        retry_count += 1
                    time.sleep(10)
                    content = ""

        except Exception as exception_instance:
            _LOGGER.error("Failed to read from the socket. {}".format(exception_instance))
        finally:
            _LOGGER.error(
                "Loop exited. No more X10 msgs will be received from Mochad.")
            if self.ctrl.socket:
                self.disconnect()
