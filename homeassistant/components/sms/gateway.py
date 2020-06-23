"""The sms gateway to interact with a GSM modem."""
import logging

import gammu  # pylint: disable=import-error, no-member
from gammu.asyncworker import (  # pylint: disable=import-error, no-member
    GammuAsyncWorker,
)

_LOGGER = logging.getLogger(__name__)


class Gateway:
    """SMS gateway to interact with a GSM modem."""

    def __init__(self, worker, hass):
        """Initialize the sms gateway."""
        self._worker = worker

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
        return gateway
    except gammu.GSMError as exc:  # pylint: disable=no-member
        _LOGGER.error("Failed to initialize, error %s", exc)
        return None
