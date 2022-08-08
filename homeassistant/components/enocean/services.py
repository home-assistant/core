"""EnOcean services."""
import logging
import queue
import time
from typing import Union

from enocean import utils
from enocean.communicators import Communicator
from enocean.protocol.constants import PACKET, RORG
from enocean.protocol.packet import Packet, UTETeachInPacket
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN
from .teachin import FourBsTeachInHandler, TeachInHandler, UteTeachInHandler
from .utils import get_communicator_reference, hex_to_list

TEACH_IN_DEVICE = "teach_in_device"  # service name
SERVICE_CALL_ATTR_TEACH_IN_SECONDS = "teach_in_time"
SERVICE_CALL_ATTR_TEACH_IN_SECONDS_DEFAULT_VALUE_STR = "60"
SERVICE_CALL_ATTR_TEACH_IN_SECONDS_DEFAULT_VALUE = 60
SERVICE_CALL_ATTR_TEACH_IN_BASE_ID_TO_USE = "teach_in_base_id"
SERVICE_CALL_TEACH_IN_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(SERVICE_CALL_ATTR_TEACH_IN_SECONDS): vol.Coerce(
                int
            ),  # teach in seconds
            vol.Optional(
                SERVICE_CALL_ATTR_TEACH_IN_BASE_ID_TO_USE
            ): vol.All(  # base id to use
                vol.Length(min=8, max=8)
            ),
        }
    )
)
SERVICE_TEACHIN_MAX_RUNTIME = 600
SERVICE_TEACHIN_STATE_VALUE_RUNNING = "RUNNING"
SERVICE_TEACHIN_STATE = "enocean.service_teachin_state"

SUPPORTED_SERVICES = TEACH_IN_DEVICE

SERVICE_TO_SCHEMA = {
    TEACH_IN_DEVICE: SERVICE_CALL_TEACH_IN_SCHEMA,
}

_LOGGER = logging.getLogger(__name__)


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for EnOcean integration."""

    services = {
        TEACH_IN_DEVICE: handle_teach_in,
    }

    def call_enocean_service(service_call: ServiceCall) -> None:
        """Call correct EnOcean service."""
        services[service_call.service](hass, service_call)
        _LOGGER.info("Service %s has been called.", str(service_call.service))

    # register the services
    service = TEACH_IN_DEVICE
    hass.services.async_register(
        DOMAIN, service, call_enocean_service, schema=SERVICE_TO_SCHEMA.get(service)
    )
    _LOGGER.debug("Request to register service %s has been sent.", str(service))


def get_teach_in_seconds(service_call: ServiceCall) -> int:
    """Get the time (in seconds) for how long the teach-in process should run."""
    teachin_for_seconds_str = service_call.data.get(
        SERVICE_CALL_ATTR_TEACH_IN_SECONDS,
        SERVICE_CALL_ATTR_TEACH_IN_SECONDS_DEFAULT_VALUE_STR,
    )
    try:
        teachin_for_seconds = int(teachin_for_seconds_str)
        # ensure the value is lower than the maximum
        teachin_for_seconds = min(SERVICE_TEACHIN_MAX_RUNTIME, teachin_for_seconds)
    except ValueError:
        teachin_for_seconds = SERVICE_CALL_ATTR_TEACH_IN_SECONDS_DEFAULT_VALUE

    return teachin_for_seconds


def get_base_id_from_service_call(service_call: ServiceCall) -> Union[str, None]:
    """Get the Base ID to use when pairing during BS4 teach-in."""
    base_id_from_call = service_call.data.get(SERVICE_CALL_ATTR_TEACH_IN_BASE_ID_TO_USE)
    return base_id_from_call


def determine_rorg_type(packet):
    """Determine the type of packet."""
    if packet is None:
        return None

    result = None
    if packet.data[0] == RORG.UTE:
        return RORG.UTE

    if packet.packet_type == PACKET.RADIO and packet.rorg == RORG.BS4:
        return RORG.BS4

    return result


def handle_teach_in(hass: HomeAssistant, service_call: ServiceCall) -> None:
    """Handle the teach-in request of a device."""

    if is_service_already_running(hass):
        return

    # set the running state to prevent the service from running twice
    hass.states.set(SERVICE_TEACHIN_STATE, SERVICE_TEACHIN_STATE_VALUE_RUNNING)

    communicator: Communicator = get_communicator_reference(hass)

    # store the originally set callback to restore it after
    # the end of the teach-in process.
    _LOGGER.debug("Storing existing callback function")
    # cb_to_restore = communicator.callback
    # the "correct" way would be to add a property to the communicator
    # to get access to the communicator. But, the enocean library seems abandoned
    cb_to_restore = communicator._Communicator__callback

    communicator._Communicator__callback = None

    try:
        # get time to run of the teach-in process from the service call
        teachin_for_seconds = get_teach_in_seconds(service_call)

        # get the base id of the transceiver module
        base_id = communicator.base_id
        _LOGGER.info("Base ID of EnOcean transceiver module: %s", str(base_id))

        # clear the receive-queue to only listen to new teach-in packets
        with communicator.receive.mutex:
            communicator.receive.queue.clear()

        teachin_start_time_seconds = time.time()

        base_id_from_service_call = get_base_id_from_service_call(service_call)

        base_id_to_use: list[int]
        if base_id_from_service_call is None:
            base_id_to_use = base_id
        else:
            base_id_to_use = hex_to_list(base_id_from_service_call)

        successful_teachin, to_be_taught_device_id = react_to_teachin_requests(
            communicator,
            hass,
            teachin_for_seconds,
            teachin_start_time_seconds,
            base_id_to_use,
        )

    finally:
        # restore callback in any case
        _LOGGER.debug("Restoring callback function")
        communicator._Communicator__callback = cb_to_restore
        # clear the state so that the service can be called again
        hass.states.set(SERVICE_TEACHIN_STATE, "")

    message, teach_in_result_msg = create_result_messages(
        successful_teachin, to_be_taught_device_id
    )

    _LOGGER.info("Teach-in was %s", teach_in_result_msg)

    # leave the notification message in the web interface
    hass.services.call(
        "persistent_notification",
        "create",
        service_data={
            "message": message,
            "title": "Result of Teach-In service call",
        },
    )


def is_service_already_running(hass):
    """Check if the service is already running."""
    service_state = hass.states.get(SERVICE_TEACHIN_STATE)
    if (
        service_state is not None
        and SERVICE_TEACHIN_STATE_VALUE_RUNNING == service_state.state
    ):
        _LOGGER.warning("Service is already running. Aborting...")


def create_result_messages(successful_teachin, to_be_taught_device_id):
    """Create both messages for UI and logger."""
    if successful_teachin:
        teach_in_result_msg = "successful. Device ID: " + str(to_be_taught_device_id)

        # message for persistent notification (success case)
        message = (
            f"EnOcean Teach-In-process successful with Device: "
            f"{str(to_be_taught_device_id)}"
        )
    else:
        # message for persistent notification (failure case)
        teach_in_result_msg = "not successful."
        message = "EnOcean Teach-In not successful."
    return message, teach_in_result_msg


def react_to_teachin_requests(
    communicator,
    hass,
    teachin_for_seconds,
    teachin_start_time_seconds,
    base_id,
):
    """Listen only for teachin-telegrams until time is over or the teachin was successful.

    Loop to empty the receive-queue.
    """

    successful_teachin = False
    to_be_taught_device_id = None

    while time.time() < teachin_start_time_seconds + teachin_for_seconds:

        # handle packet --> learn device
        # how? reacting to signals from alternative callback? Currently, not.
        # getting the receive-queue? yes
        # One could exchange the callback handler during the teach-in, maybe

        # Currently, there is no callback handler (we set it to None), so there can be
        # packets in the receive-queue. Try to process them.
        try:
            # get the packets from the communicator and check whether they are teachin packets
            packet: Packet = communicator.receive.get(block=True, timeout=1)

            rorg_type = determine_rorg_type(packet)

            _LOGGER.debug(str(packet))
            if isinstance(packet, UTETeachInPacket):
                # THINK: handler, maybe deactivate teach in before and handle it the "handler"
                handler: TeachInHandler = UteTeachInHandler()
                (
                    successful_sent,
                    to_be_taught_device_id,
                ) = handler.handle_teach_in_request(hass, packet, communicator)
                return successful_sent, to_be_taught_device_id

            # if packet.packet_type == PACKET.RADIO_ERP1 and packet.rorg == RORG.BS4:
            if rorg_type == RORG.BS4:
                _LOGGER.debug("Received BS4 packet")
                # get the third bit of the fourth byte and check for "0".
                if is_bs4_teach_in_packet(packet):
                    # we have a teach-in packet
                    # let's create a proper response
                    handler: TeachInHandler = FourBsTeachInHandler()
                    handler.set_base_id(base_id)

                    (
                        successful_sent,
                        to_be_taught_device_id,
                    ) = handler.handle_teach_in_request(hass, packet, communicator)

                    if successful_sent:
                        # the package was put to the transmit queue
                        _LOGGER.info("Sent teach-in response via communicator")
                        successful_teachin = True
                        break
            else:
                # packet type not relevant to teach-in process
                # drop it. Re-injection into the queue doesn't make sense here. Eventually one
                # could save them all for later usage?
                continue
        except queue.Empty:
            continue
    if to_be_taught_device_id is not None:
        _LOGGER.info("Device ID of paired device: %s", to_be_taught_device_id)
    if not successful_teachin:
        _LOGGER.info("Teach-In time is over.")
    return successful_teachin, to_be_taught_device_id


def is_bs4_teach_in_packet(packet):
    """Checker whether it's a 4BS packet."""
    return len(packet.data) > 3 and utils.get_bit(packet.data[4], 3) == 0
