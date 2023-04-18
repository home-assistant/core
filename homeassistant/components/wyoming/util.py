"""Utilities for Wyoming integration."""
import asyncio

import async_timeout
from wyoming.event import async_read_event, async_write_event
from wyoming.info import Describe, Info

from .error import WyomingError

_INFO_TIMEOUT = 1


async def get_wyoming_info(host: str, port: int) -> Info:
    """Retrieve information about Wyoming service."""
    with async_timeout.timeout(_INFO_TIMEOUT):
        reader, writer = await asyncio.open_connection(
            host,
            port,
        )

        await async_write_event(Describe().event(), writer)
        while True:
            event = await async_read_event(reader)
            if event is None:
                raise WyomingError(f"Failed to get info from {host}:{port}")

            if Info.is_type(event.type):
                return Info.from_event(event)
