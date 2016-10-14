"""
Component that connects to a Nuimo device over Bluetooth LE.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/nuimo_controller/
"""
import logging
import threading
import time
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_MAC, CONF_NAME, EVENT_HOMEASSISTANT_STOP)

REQUIREMENTS = [
    '--only-binary=all '  # avoid compilation of gattlib
    'git+https://github.com/getSenic/nuimo-linux-python'
    '#nuimo==1.0.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'nuimo_controller'
EVENT_NUIMO = 'nuimo_input'

DEFAULT_NAME = 'None'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_MAC): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)

SERVICE_NUIMO = 'led_matrix'
DEFAULT_INTERVAL = 2.0

SERVICE_NUIMO_SCHEMA = vol.Schema({
    vol.Required('matrix'): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional('interval', default=DEFAULT_INTERVAL): float
})

DEFAULT_ADAPTER = 'hci0'


def setup(hass, config):
    """Setup the Nuimo component."""
    conf = config[DOMAIN]
    mac = conf.get(CONF_MAC)
    name = conf.get(CONF_NAME)
    NuimoThread(hass, mac, name).start()
    return True


class NuimoLogger(object):  # pylint: disable=too-few-public-methods
    """Handle Nuimo Controller event callbacks."""

    def __init__(self, hass, name):
        """Initialize Logger object."""
        self._hass = hass
        self._name = name

    def received_gesture_event(self, event):
        """Input Event received."""
        _LOGGER.debug("received event: name=%s, gesture_id=%s,value=%s",
                      event.name, event.gesture, event.value)
        self._hass.bus.fire(EVENT_NUIMO,
                            {'type': event.name, 'value': event.value,
                             'name': self._name})


class NuimoThread(threading.Thread):
    """Manage one Nuimo controller."""

    def __init__(self, hass, mac, name):
        """Initialize thread object."""
        super(NuimoThread, self).__init__()
        self._hass = hass
        self._mac = mac
        self._name = name
        self._hass_is_running = True
        self._nuimo = None
        self._listener = hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                                              self.stop)

    def run(self):
        """Setup connection or be idle."""
        while self._hass_is_running:
            if not self._nuimo or not self._nuimo.is_connected():
                self._attach()
                self._connect()
            else:
                time.sleep(1)

        if self._nuimo:
            self._nuimo.disconnect()
            self._nuimo = None

    def stop(self, event):  # pylint: disable=unused-argument
        """Terminate Thread by unsetting flag."""
        _LOGGER.debug('Stopping thread for Nuimo %s', self._mac)
        self._hass_is_running = False
        self._hass.bus.remove_listener(EVENT_HOMEASSISTANT_STOP,
                                       self._listener)

    def _attach(self):
        """Create a nuimo object from mac address or discovery."""
        # pylint: disable=import-error
        from nuimo import NuimoController, NuimoDiscoveryManager

        if self._nuimo:
            self._nuimo.disconnect()
            self._nuimo = None

        if self._mac:
            self._nuimo = NuimoController(self._mac)
        else:
            nuimo_manager = NuimoDiscoveryManager(
                bluetooth_adapter=DEFAULT_ADAPTER, delegate=DiscoveryLogger())
            nuimo_manager.start_discovery()
            # Were any Nuimos found?
            if not nuimo_manager.nuimos:
                _LOGGER.debug('No Nuimos detected')
                return
            # Take the first Nuimo found.
            self._nuimo = nuimo_manager.nuimos[0]
            self._mac = self._nuimo.addr

    def _connect(self):
        """Build up connection and set event delegator and service."""
        if not self._nuimo:
            return

        try:
            self._nuimo.connect()
            _LOGGER.debug('connected to %s', self._mac)
        except RuntimeError as error:
            _LOGGER.error('could not connect to %s: %s', self._mac, error)
            time.sleep(1)
            return

        nuimo_event_delegate = NuimoLogger(self._hass, self._name)
        self._nuimo.set_delegate(nuimo_event_delegate)

        def handle_write_matrix(call):
            """Handle led matrix service."""
            matrix = call.data.get('matrix', None)
            name = call.data.get(CONF_NAME, DEFAULT_NAME)
            interval = call.data.get('interval', DEFAULT_INTERVAL)
            if self._name == name and matrix:
                self._nuimo.write_matrix(matrix, interval)

        self._hass.services.register(DOMAIN, SERVICE_NUIMO,
                                     handle_write_matrix,
                                     schema=SERVICE_NUIMO_SCHEMA)

        self._nuimo.write_matrix(HOMEASSIST_LOGO, 2.0)


# must be 9x9 matrix
HOMEASSIST_LOGO = (
    "    .    " +
    "   ...   " +
    "  .....  " +
    " ....... " +
    "..... ..." +
    " ....... " +
    " .. .... " +
    " .. .... " +
    ".........")


class DiscoveryLogger(object):
    """Handle Nuimo Discovery callbacks."""

    def discovery_started(self):  # pylint: disable=no-self-use
        """Discovery startet."""
        _LOGGER.info("started discovery")

    def discovery_finished(self):  # pylint: disable=no-self-use
        """Discovery finished."""
        _LOGGER.info("finished discovery")

    def controller_added(self, nuimo):  # pylint: disable=no-self-use
        """Controller found."""
        _LOGGER.info("added Nuimo: %s", nuimo)
