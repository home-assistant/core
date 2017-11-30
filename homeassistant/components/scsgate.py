"""
Support for SCSGate components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/scsgate/
"""
import logging
from threading import Lock

import voluptuous as vol

from homeassistant.const import (CONF_DEVICE, CONF_NAME)
from homeassistant.core import EVENT_HOMEASSISTANT_STOP
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['scsgate==0.1.0']

_LOGGER = logging.getLogger(__name__)

ATTR_STATE = 'state'

CONF_SCS_ID = 'scs_id'

DOMAIN = 'scsgate'

SCSGATE = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

SCSGATE_SCHEMA = vol.Schema({
    vol.Required(CONF_SCS_ID): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})


def setup(hass, config):
    """Set up the SCSGate component."""
    device = config[DOMAIN][CONF_DEVICE]
    global SCSGATE

    # pylint: disable=broad-except
    try:
        SCSGATE = SCSGate(device=device, logger=_LOGGER)
        SCSGATE.start()
    except Exception as exception:
        _LOGGER.error("Cannot setup SCSGate component: %s", exception)
        return False

    def stop_monitor(event):
        """Stop the SCSGate."""
        _LOGGER.info("Stopping SCSGate monitor thread")
        SCSGATE.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_monitor)

    return True


class SCSGate(object):
    """The class for dealing with the SCSGate device via scsgate.Reactor."""

    def __init__(self, device, logger):
        """Initialize the SCSGate."""
        self._logger = logger
        self._devices = {}
        self._devices_to_register = {}
        self._devices_to_register_lock = Lock()
        self._device_being_registered = None
        self._device_being_registered_lock = Lock()

        from scsgate.connection import Connection
        connection = Connection(device=device, logger=self._logger)

        from scsgate.reactor import Reactor
        self._reactor = Reactor(
            connection=connection, logger=self._logger,
            handle_message=self.handle_message)

    def handle_message(self, message):
        """Handle a messages seen on the bus."""
        from scsgate.messages import StateMessage, ScenarioTriggeredMessage

        self._logger.debug("Received message {}".format(message))
        if not isinstance(message, StateMessage) and \
           not isinstance(message, ScenarioTriggeredMessage):
            msg = "Ignored message {} - not releavant type".format(
                message)
            self._logger.debug(msg)
            return

        if message.entity in self._devices:
            new_device_activated = False
            with self._devices_to_register_lock:
                if message.entity == self._device_being_registered:
                    self._device_being_registered = None
                    new_device_activated = True
            if new_device_activated:
                self._activate_next_device()

            # pylint: disable=broad-except
            try:
                self._devices[message.entity].process_event(message)
            except Exception as exception:
                msg = "Exception while processing event: {}".format(exception)
                self._logger.error(msg)
        else:
            self._logger.info(
                "Ignoring state message for device {} because unknonw".format(
                    message.entity))

    @property
    def devices(self):
        """Return a dictionary with known devices.

        Key is device ID, value is the device itself.
        """
        return self._devices

    def add_device(self, device):
        """Add the specified device.

        The list contain already registered ones.
        Beware: this is not what you usually want to do, take a look at
        `add_devices_to_register`
        """
        self._devices[device.scs_id] = device

    def add_devices_to_register(self, devices):
        """List of devices to be registered."""
        with self._devices_to_register_lock:
            for device in devices:
                self._devices_to_register[device.scs_id] = device
        self._activate_next_device()

    def _activate_next_device(self):
        """Start the activation of the first device."""
        from scsgate.tasks import GetStatusTask

        with self._devices_to_register_lock:
            while self._devices_to_register:
                _, device = self._devices_to_register.popitem()
                self._devices[device.scs_id] = device
                self._device_being_registered = device.scs_id
                self._reactor.append_task(GetStatusTask(target=device.scs_id))

    def is_device_registered(self, device_id):
        """Check whether a device is already registered or not."""
        with self._devices_to_register_lock:
            if device_id in self._devices_to_register.keys():
                return False

        with self._device_being_registered_lock:
            if device_id == self._device_being_registered:
                return False

        return True

    def start(self):
        """Start the scsgate.Reactor."""
        self._reactor.start()

    def stop(self):
        """Stop the scsgate.Reactor."""
        self._reactor.stop()

    def append_task(self, task):
        """Register a new task to be executed."""
        self._reactor.append_task(task)
