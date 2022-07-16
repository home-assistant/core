"""The sms gateway to interact with a GSM modem."""
import logging

import gammu  # pylint: disable=import-error
from gammu.asyncworker import GammuAsyncWorker  # pylint: disable=import-error

from homeassistant.core import callback

from .const import DOMAIN, SMS_STATE_UNREAD

_LOGGER = logging.getLogger(__name__)


class Gateway:
    """SMS gateway to interact with a GSM modem."""

    def __init__(self, config, hass):
        """Initialize the sms gateway."""
        _LOGGER.debug("Init with connection mode:%s", config["Connection"])
        self._worker = GammuAsyncWorker(self.sms_pull)
        self._worker.configure(config)
        self._hass = hass
        self._first_pull = True

    async def init_async(self):
        """Initialize the sms gateway asynchronously."""
        await self._worker.init_async()

    def sms_pull(self, state_machine):
        """Pull device.

        @param state_machine: state machine
        @type state_machine: gammu.StateMachine
        """
        state_machine.ReadDevice()

        _LOGGER.debug("Pulling modem")
        self.sms_read_messages(state_machine, self._first_pull)
        self._first_pull = False

    def sms_read_messages(self, state_machine, force=False):
        """Read all received SMS messages.

        @param state_machine: state machine which invoked action
        @type state_machine: gammu.StateMachine
        """
        entries = self.get_and_delete_all_sms(state_machine, force)
        _LOGGER.debug("SMS entries:%s", entries)
        data = []

        for entry in entries:
            decoded_entry = gammu.DecodeSMS(entry)
            message = entry[0]
            _LOGGER.debug("Processing sms:%s,decoded:%s", message, decoded_entry)
            sms_state = message["State"]
            _LOGGER.debug("SMS state:%s", sms_state)
            if sms_state == SMS_STATE_UNREAD:
                if decoded_entry is None:
                    text = message["Text"]
                else:
                    text = ""
                    for inner_entry in decoded_entry["Entries"]:
                        if inner_entry["Buffer"] is not None:
                            text += inner_entry["Buffer"]

                event_data = {
                    "phone": message["Number"],
                    "date": str(message["DateTime"]),
                    "message": text,
                }

                _LOGGER.debug("Append event data:%s", event_data)
                data.append(event_data)

        self._hass.add_job(self._notify_incoming_sms, data)

    def get_and_delete_all_sms(self, state_machine, force=False):
        """Read and delete all SMS in the modem."""
        # Read SMS memory status ...
        memory = state_machine.GetSMSStatus()
        # ... and calculate number of messages
        remaining = memory["SIMUsed"] + memory["PhoneUsed"]
        start_remaining = remaining
        # Get all sms
        start = True
        entries = []
        all_parts = -1
        all_parts_arrived = False
        _LOGGER.debug("Start remaining:%i", start_remaining)

        try:
            while remaining > 0:
                if start:
                    entry = state_machine.GetNextSMS(Folder=0, Start=True)
                    all_parts = entry[0]["UDH"]["AllParts"]
                    part_number = entry[0]["UDH"]["PartNumber"]
                    is_single_part = all_parts == 0
                    is_multi_part = 0 <= all_parts < start_remaining
                    _LOGGER.debug("All parts:%i", all_parts)
                    _LOGGER.debug("Part Number:%i", part_number)
                    _LOGGER.debug("Remaining:%i", remaining)
                    all_parts_arrived = is_multi_part or is_single_part
                    _LOGGER.debug("Start all_parts_arrived:%s", all_parts_arrived)
                    start = False
                else:
                    entry = state_machine.GetNextSMS(
                        Folder=0, Location=entry[0]["Location"]
                    )

                if all_parts_arrived or force:
                    remaining = remaining - 1
                    entries.append(entry)

                    # delete retrieved sms
                    _LOGGER.debug("Deleting message")
                    try:
                        state_machine.DeleteSMS(Folder=0, Location=entry[0]["Location"])
                    except gammu.ERR_MEMORY_NOT_AVAILABLE:
                        _LOGGER.error("Error deleting SMS, memory not available")
                else:
                    _LOGGER.debug("Not all parts have arrived")
                    break

        except gammu.ERR_EMPTY:
            # error is raised if memory is empty (this induces wrong reported
            # memory status)
            _LOGGER.info("Failed to read messages!")

        # Link all SMS when there are concatenated messages
        entries = gammu.LinkSMS(entries)

        return entries

    @callback
    def _notify_incoming_sms(self, messages):
        """Notify hass when an incoming SMS message is received."""
        for message in messages:
            event_data = {
                "phone": message["phone"],
                "date": message["date"],
                "text": message["message"],
            }
            self._hass.bus.async_fire(f"{DOMAIN}.incoming_sms", event_data)

    async def send_sms_async(self, message):
        """Send sms message via the worker."""
        return await self._worker.send_sms_async(message)

    async def get_imei_async(self):
        """Get the IMEI of the device."""
        return await self._worker.get_imei_async()

    async def get_signal_quality_async(self):
        """Get the current signal level of the modem."""
        return await self._worker.get_signal_quality_async()

    async def get_network_info_async(self):
        """Get the current network info of the modem."""
        return await self._worker.get_network_info_async()

    async def terminate_async(self):
        """Terminate modem connection."""
        return await self._worker.terminate_async()


async def create_sms_gateway(config, hass):
    """Create the sms gateway."""
    try:
        gateway = Gateway(config, hass)
        await gateway.init_async()
        return gateway
    except gammu.GSMError as exc:
        _LOGGER.error("Failed to initialize, error %s", exc)
        return None
