"""Base class for Wyoming providers."""
import asyncio
import logging

import async_timeout
from wyoming.client import AsyncTcpClient
from wyoming.info import Describe, Info

from .error import WyomingError

_LOGGER = logging.getLogger(__name__)
_INFO_TIMEOUT = 1
_INFO_RETRY_WAIT = 2
_INFO_RETRIES = 3


async def load_wyoming_info(host: str, port: int) -> Info | None:
    """Load info from Wyoming server."""
    wyoming_info: Info | None = None

    for _ in range(_INFO_RETRIES):
        try:
            async with AsyncTcpClient(host, port) as client:
                with async_timeout.timeout(_INFO_TIMEOUT):
                    # Describe -> Info
                    await client.write_event(Describe().event())
                    while True:
                        event = await client.read_event()
                        if event is None:
                            raise WyomingError("Connection closed unexpectedly")

                        if Info.is_type(event.type):
                            wyoming_info = Info.from_event(event)
                            break
        except (asyncio.TimeoutError, OSError, WyomingError):
            # Sleep and try again
            await asyncio.sleep(_INFO_RETRY_WAIT)

    return wyoming_info
