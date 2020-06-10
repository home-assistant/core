"""The sms gateway to interact with a GSM modem."""
from asyncio import get_running_loop
import logging

import gammu  # pylint: disable=import-error, no-member

from .gammuasync import GammuAsyncWorker

_LOGGER = logging.getLogger(__name__)


class Gateway:
    """SMS gateway to interact with a GSM modem."""

    def __init__(self, worker, loop, hass):
        """Initialize the sms gateway."""
        self._worker = worker

    async def send_sms_async(self, message):
        """Send sms message via the worker."""
        return await self._worker.send_sms_async(message)

    async def terminate_async(self):
        """Terminate modem connection."""
        return await self._worker.terminate_async()


async def create_sms_gateway(config, hass):
    """Create the sms gateway."""
    try:
        worker = GammuAsyncWorker(get_running_loop())
        worker.configure(config)
        await worker.init_async()
        gateway = Gateway(worker, get_running_loop(), hass)
        return gateway
    except gammu.GSMError as exc:  # pylint: disable=no-member
        _LOGGER.error("Failed to initialize, error %s", exc)
        return None
