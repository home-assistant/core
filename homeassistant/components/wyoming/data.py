"""Base class for Wyoming providers."""
from __future__ import annotations

import asyncio

import async_timeout
from wyoming.client import AsyncTcpClient
from wyoming.info import Describe, Info

from homeassistant.const import Platform

from .error import WyomingError

_INFO_TIMEOUT = 1
_INFO_RETRY_WAIT = 2
_INFO_RETRIES = 3


class WyomingService:
    """Hold info for Wyoming service."""

    def __init__(self, host: str, port: int, info: Info) -> None:
        """Initialize Wyoming service."""
        self.host = host
        self.port = port
        self.info = info
        platforms = []
        if info.asr:
            platforms.append(Platform.STT)
        self.platforms = platforms

    @classmethod
    async def create(cls, host: str, port: int) -> WyomingService | None:
        """Create a Wyoming service."""
        info = await load_wyoming_info(host, port)
        if info is None:
            return None

        return cls(host, port, info)


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
                            raise WyomingError(
                                "Connection closed unexpectedly",
                            )

                        if Info.is_type(event.type):
                            wyoming_info = Info.from_event(event)
                            break
        except (asyncio.TimeoutError, OSError, WyomingError):
            # Sleep and try again
            await asyncio.sleep(_INFO_RETRY_WAIT)

    return wyoming_info
