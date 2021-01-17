"""Support for SCSGate components."""
import logging
from threading import Lock

from scsgate.connection import Connection
from scsgate.messages import ScenarioTriggeredMessage, StateMessage
from scsgate.reactor import Reactor
from scsgate.tasks import GetStatusTask
import voluptuous as vol

from homeassistant.const import CONF_DEVICE, CONF_NAME
from homeassistant.core import EVENT_HOMEASSISTANT_STOP
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_SCS_ID = "scs_id"

DOMAIN = "scsgate"

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DEVICE): cv.string})}, extra=vol.ALLOW_EXTRA
)

SCSGATE_SCHEMA = vol.Schema(
    {vol.Required(CONF_SCS_ID): cv.string, vol.Optional(CONF_NAME): cv.string}
)


def setup(hass, config):
    """Set up the SCSGate component."""
    device = config[DOMAIN][CONF_DEVICE]
    scsgate = None

    try:
        scsgate = SCSGate(device=device, logger=_LOGGER)
        scsgate.start()
    except Exception as exception:  # pylint: disable=broad-except
        _LOGGER.error("Cannot setup SCSGate component: %s", exception)
        return False

    def stop_monitor(event):
        """Stop the SCSGate."""
        _LOGGER.info("Stopping SCSGate monitor thread")
        scsgate.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_monitor)
    hass.data[DOMAIN] = scsgate

    return True


class SCSGate:
    """The class for dealing with the SCSGate device via scsgate.Reactor."""

    def __init__(self, device, logger):
        """Initialize the SCSGate."""
        self._logger = logger
        self._devices = {}
        self._devices_to_register = {}
        self._devices_to_register_lock = Lock()
        self._device_being_registered = None
        self._device_being_registered_lock = Lock()

        connection = Connection(device=device, logger=self._logger)

        self._reactor = Reactor(
            connection=connection,
            logger=self._logger,
            handle_message=self.handle_message,
        )

    def handle_message(self, message):
        """Handle a messages seen on the bus."""

        self._logger.debug(f"Received message {message}")
        if not isinstance(message, StateMessage) and not isinstance(
            message, ScenarioTriggeredMessage
        ):
            msg = f"Ignored message {message} - not relevant type"
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

            try:
                self._devices[message.entity].process_event(message)
            except Exception as exception:  # pylint: disable=broad-except
                msg = f"Exception while processing event: {exception}"
                self._logger.error(msg)
        else:
            self._logger.info(
                "Ignoring state message for device {} because unknown".format(
                    message.entity
                )
            )

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

        with self._devices_to_register_lock:
            while self._devices_to_register:
                _, device = self._devices_to_register.popitem()
                self._devices[device.scs_id] = device
                self._device_being_registered = device.scs_id
                self._reactor.append_task(GetStatusTask(target=device.scs_id))

    def is_device_registered(self, device_id):
        """Check whether a device is already registered or not."""
        with self._devices_to_register_lock:
            if device_id in self._devices_to_register:
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
