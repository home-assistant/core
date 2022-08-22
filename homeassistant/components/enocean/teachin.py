"""Support for Teach-In process."""
from abc import ABC, abstractmethod
import logging

from enocean.communicators import Communicator
from enocean.protocol.constants import PACKET
from enocean.protocol.packet import Packet, RadioPacket

from homeassistant.core import HomeAssistant


class TeachInHandler(ABC):
    """Interface for various teach-in requests."""

    def __init__(self):
        """Init the Handler."""
        self.base_id = None
        self.logger = logging.getLogger(__name__)

    def set_base_id(self, base_id):
        """Set the base id of the teach-in handler."""
        self.base_id = base_id

    @abstractmethod
    def handle_teach_in_request(
        self, hass: HomeAssistant, packet: Packet, communicator: Communicator
    ):
        """Abstract method for handling incoming teach-in requests."""


class UteTeachInHandler(TeachInHandler):
    """Implementation to handle UTE teach-in requests."""

    def handle_teach_in_request(
        self, hass: HomeAssistant, packet: RadioPacket, communicator: Communicator
    ):
        """Handle the UTE-type teach-in request."""
        self.logger.info(
            "New device learned! The ID is Hex: %s. Sender: %s",
            packet.sender_hex,
            str(packet.sender_int),
        )

        to_be_taught_device_id = packet.sender
        successful_teachin = True

        return successful_teachin, to_be_taught_device_id


class FourBsTeachInHandler(TeachInHandler):
    """Implementation to handle 4BS teach-in requests."""

    def handle_teach_in_request(
        self, hass: HomeAssistant, packet: Packet, communicator: Communicator
    ):
        """Handle the 4BS-type teach-in request."""
        rorg = packet.rorg
        func = packet.rorg_func
        rorg_type = packet.rorg_type
        teach_in_response_packet: RadioPacket = Packet.create(
            PACKET.RADIO,
            # respond with 4BS teach-in-response
            rorg=rorg,  # RORG.BS4
            rorg_func=func,
            rorg_type=rorg_type,
            sender=communicator.base_id,
            learn=True,
        )

        # copy over the packet data as it will be sent back with slight variation
        teach_in_response_packet.data[1:5] = packet.data[1:5]

        # set the bits of the byte for the success case (F0 = 11110000)
        teach_in_response_packet.data[4] = 0xF0

        # set destination of response to former sender
        destination = packet.data[-5:-1]
        # is this the sender?
        self.logger.info("Former sender: %s", destination)
        to_be_taught_device_id = destination
        teach_in_response_packet.destination = destination

        # set sender to base id (no offset)
        self.logger.info("Base ID to use: %s", str(self.base_id))
        teach_in_response_packet.sender = self.base_id

        # build the optional data
        # subTelegram Number + destination + dBm (send case: FF) + security (0)
        optional = [3] + destination + [0xFF, 0]
        teach_in_response_packet.optional = optional
        teach_in_response_packet.parse()
        self.logger.info("4BS teach-in response created")

        # send the packet via the communicator
        successful_sent = communicator.send(teach_in_response_packet)

        return successful_sent, to_be_taught_device_id
