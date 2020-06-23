"""The sms gateway to interact with a GSM modem."""
import asyncio
import logging

import gammu  # pylint: disable=import-error, no-member
from gammu.asyncworker import (  # pylint: disable=import-error, no-member
    GammuAsyncWorker,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class Gateway:
    """SMS gateway to interact with a GSM modem."""

    def __init__(self, worker, hass):
        """Initialize the sms gateway."""
        self._worker = worker
        self._loop = asyncio.get_running_loop()
        self._hass = hass

    async def init_async(self):
        """Initialize the sms gateway asynchronously."""
        try:
            await self._worker.SetIncomingSMSAsync()
        except gammu.ERR_NOTSUPPORTED:
            _LOGGER.warning("Your phone does not support incoming SMS notifications!")
        else:
            await self._worker.SetIncomingCallbackAsync(self.sms_callback)

    def sms_callback(self, state_machine, callback_type, callback_data):
        """Receive notification about incoming event.

        @param state_machine: state machine which invoked action
        @type state_machine: gammu.StateMachine
        @param callback_type: type of action, one of Call, SMS, CB, USSD
        @type callback_type: string
        @param data: event data
        @type data: hash
        """
        _LOGGER.debug(
            f"Received incoming event type:{callback_type}, data:{callback_data}"
        )
        entries = self.get_and_delete_all_sms(state_machine)
        _LOGGER.debug(f"SMS entries:{entries}")
        data = list()

        for entry in entries:
            v = gammu.DecodeSMS(entry)
            message = entry[0]
            _LOGGER.debug(f"Processing sms {message}, decoded: {v}")
            if v is None:
                text = message["Text"]
            else:
                text = ""
                for e in v["Entries"]:
                    if e["Buffer"] is not None:
                        text = text + e["Buffer"]

            event_data = dict(
                phone=message["Number"], date=str(message["DateTime"]), message=text
            )

            _LOGGER.debug(f"Append event data:{event_data}")
            data.append(event_data)

        self._loop.call_soon_threadsafe(self._notify_incoming_sms, data)

    def get_and_delete_all_sms(self, state_machine, force=False):
        """Read and delete all SMS in the modem."""
        # Read SMS memory status ...
        memory = state_machine.GetSMSStatus()
        # ... and calculate number of messages
        remaining = memory["SIMUsed"] + memory["PhoneUsed"]
        startRemaining = remaining
        # Get all sms
        start = True
        entries = list()
        allParts = -1
        allPartsArrived = False
        _LOGGER.debug(f"Start remaining:{startRemaining}")

        try:
            while remaining > 0:
                if start:
                    entry = state_machine.GetNextSMS(Folder=0, Start=True)
                    allParts = entry[0]["UDH"]["AllParts"]
                    partNumber = entry[0]["UDH"]["PartNumber"]
                    isSinglePart = allParts == 0
                    isMultiPart = (allParts > 0) and (startRemaining >= allParts)
                    _LOGGER.debug(f"All parts:{allParts}")
                    _LOGGER.debug(f"Part Number:{partNumber}")
                    _LOGGER.debug(f"Remaining:{remaining}")
                    allPartsArrived = isMultiPart or isSinglePart
                    _LOGGER.debug(f"start allPartsArrived:{allPartsArrived}")
                    start = False
                else:
                    entry = state_machine.GetNextSMS(
                        Folder=0, Location=entry[0]["Location"]
                    )

                if allPartsArrived or force:
                    remaining = remaining - 1
                    entries.append(entry)

                    # delete retrieved sms
                    _LOGGER.debug("Deleting message")
                    state_machine.DeleteSMS(Folder=0, Location=entry[0]["Location"])
                else:
                    _LOGGER.debug("Not all parts have arrived")
                    break

        except gammu.ERR_EMPTY:
            # error is raised if memory is empty (this induces wrong reported
            # memory status)
            _LOGGER.warning("Failed to read messages!")

        # Link all SMS when there are concatenated messages
        entries = gammu.LinkSMS(entries)

        return entries

    def _notify_incoming_sms(self, messages):
        """Notify hass when an incoming SMS message is received."""
        for message in messages:
            event_data = {
                "phone": message["phone"],
                "date": message["date"],
                "text": message["message"],
            }
            _LOGGER.debug(f"Firing event:{event_data}")
            self._hass.bus.fire(f"{DOMAIN}.incoming_sms", event_data)

    async def send_sms_async(self, message):
        """Send sms message via the worker."""
        return await self._worker.send_sms_async(message)

    async def get_imei_async(self):
        """Get the IMEI of the device."""
        return await self._worker.get_imei_async()

    async def terminate_async(self):
        """Terminate modem connection."""
        return await self._worker.terminate_async()


async def create_sms_gateway(config, hass):
    """Create the sms gateway."""
    try:
        worker = GammuAsyncWorker()
        worker.configure(config)
        await worker.init_async()
        gateway = Gateway(worker, hass)
        await gateway.init_async()
        return gateway
    except gammu.GSMError as exc:  # pylint: disable=no-member
        _LOGGER.error("Failed to initialize, error %s", exc)
        return None
