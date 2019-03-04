"""Support for EnOcean devices."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_DEVICE
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'enocean'

ENOCEAN_DONGLE = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the EnOcean component."""
    global ENOCEAN_DONGLE

    serial_dev = config[DOMAIN].get(CONF_DEVICE)

    ENOCEAN_DONGLE = EnOceanDongle(hass, serial_dev)

    return True


class EnOceanDongle:
    """Representation of an EnOcean dongle."""

    def __init__(self, hass, ser):
        """Initialize the EnOcean dongle."""
        from enocean.communicators.serialcommunicator import SerialCommunicator
        self.__communicator = SerialCommunicator(
            port=ser, callback=self.callback)
        self.__communicator.start()
        self.__devices = []

    def register_device(self, dev):
        """Register another device."""
        self.__devices.append(dev)

    def send_command(self, command):
        """Send a command from the EnOcean dongle."""
        self.__communicator.send(command)

    def callback(self, packet):
        """Handle EnOcean device's callback.

        This is the callback function called by python-enocan whenever there
        is an incoming packet.
        """
        from enocean.protocol.packet import RadioPacket
        from enocean.utils import combine_hex
        if isinstance(packet, RadioPacket):
            _LOGGER.debug("Received radio packet: %s", packet)
            for device in self.__devices:
                if packet.sender_int == combine_hex(device.dev_id):
                    device.value_changed(packet)


class EnOceanDevice:
    """Parent class for all devices associated with the EnOcean component."""

    def __init__(self, dev_id, dev_name="EnOcean device"):
        """Initialize the device."""
        ENOCEAN_DONGLE.register_device(self)
        self.dev_id = dev_id
        self.dev_name = dev_name

    def value_changed(self, packet):
        """Update the internal state of the device when a packet arrives."""

    # pylint: disable=no-self-use
    def send_command(self, data, optional, packet_type):
        """Send a command via the EnOcean dongle."""
        from enocean.protocol.packet import Packet
        packet = Packet(packet_type, data=data, optional=optional)
        ENOCEAN_DONGLE.send_command(packet)
