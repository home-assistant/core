"""Base class for Wyoming providers."""
import asyncio
import logging

import async_timeout
from wyoming.client import AsyncTcpClient
from wyoming.info import Describe, Info

from .error import WyomingError

_LOGGER = logging.getLogger(__name__)
_INFO_TIMEOUT = 5
_INFO_RETRY = 3


async def load_wyoming_info(host: str, port: int) -> Info | None:
    """Load info from Wyoming server."""
    wyoming_info: Info | None = None

    while wyoming_info is None:
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
            await asyncio.sleep(_INFO_RETRY)

    if wyoming_info is None:
        _LOGGER.warning(
            "Failed to get info from Wyoming server %s:%s",
            host,
            port,
        )
        return None

    return wyoming_info
