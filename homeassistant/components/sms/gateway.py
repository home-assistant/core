"""The sms gateway to interact with a GSM modem."""
import logging

import gammu

from .gammuasync import GammuAsyncWorker

_LOGGER = logging.getLogger(__name__)


class Gateway:
    """SMS gateway to interact with a GSM modem."""

    def __init__(self, worker, loop, callback):
        """Initialize the sms gateway."""
        self._worker = worker
        self._loop = loop
        self._callback = callback

    async def _init(self):
        """Initialize the sms gateway asyncronisly."""
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

        data = list()

        for entry in entries:
            v = gammu.DecodeSMS(entry)
            message = entry[0]
            _LOGGER.debug("Processing sms %s, decoded: %s", message, v)
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

            data.insert(event_data)

        self._loop.call_soon_threadsafe(self._callback, data)

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
        print("Start remaining:", remaining)

        try:
            while remaining > 0:
                if start:
                    entry = state_machine.GetNextSMS(Folder=0, Start=True)
                    allParts = entry[0]["UDH"]["AllParts"]
                    partNumber = entry[0]["UDH"]["PartNumber"]
                    isSinglePart = allParts == 0
                    isMultiPart = (allParts > 0) and (startRemaining >= allParts)
                    print("All parts:", allParts)
                    print("Part Number:", partNumber)
                    print("Remaining:", remaining)
                    allPartsArrived = isMultiPart or isSinglePart
                    print("start allPartsArrived:", allPartsArrived)
                    start = False
                else:
                    entry = state_machine.GetNextSMS(
                        Folder=0, Location=entry[0]["Location"]
                    )

                if allPartsArrived or force:
                    remaining = remaining - 1
                    entries.append(entry)

                    # delete retrieved sms
                    print("Deleting message")
                    state_machine.DeleteSMS(Folder=0, Location=entry[0]["Location"])
                else:
                    print("Not all parts have arrived")
                    break

        except gammu.ERR_EMPTY:
            # error is raised if memory is empty (this induces wrong reported
            # memory status)
            print("Failed to read messages!")

        # Link all SMS when there are concatenated messages
        entries = gammu.LinkSMS(entries)

        return entries

    async def GetSignalQualityAsync(self):
        """Get the current signal quality of the gsm modem."""
        return await self._worker.GetSignalQualityAsync()

    async def SendSMSAsync(self, message):
        """Send sms message via the worker."""
        return await self._worker.SendSMSAsync(message)


async def create_sms_gateway(config, loop, callback):
    """Create the sms gateway."""
    try:
        worker = GammuAsyncWorker(loop)
        worker.configure(config)
        await worker.InitAsync()
        gateway = Gateway(worker, loop, callback)
        await gateway._init()
        return gateway
    except gammu.GSMError as exc:  # pylint: disable=no-member
        _LOGGER.error("Failed to initialize, error %s", exc)
        return 0
