"""Base class for Wyoming providers."""
from __future__ import annotations

import asyncio

from wyoming.client import AsyncTcpClient
from wyoming.info import Describe, Info, Satellite

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
        if any(asr.installed for asr in info.asr):
            platforms.append(Platform.STT)
        if any(tts.installed for tts in info.tts):
            platforms.append(Platform.TTS)
        if any(wake.installed for wake in info.wake):
            platforms.append(Platform.WAKE_WORD)
        self.platforms = platforms

    def has_services(self) -> bool:
        """Return True if services are installed that Home Assistant can use."""
        return (
            any(asr for asr in self.info.asr if asr.installed)
            or any(tts for tts in self.info.tts if tts.installed)
            or any(wake for wake in self.info.wake if wake.installed)
            or ((self.info.satellite is not None) and self.info.satellite.installed)
        )

    def get_name(self) -> str | None:
        """Return name of first installed usable service."""
        # ASR = automated speech recognition (speech-to-text)
        asr_installed = [asr for asr in self.info.asr if asr.installed]
        if asr_installed:
            return asr_installed[0].name

        # TTS = text-to-speech
        tts_installed = [tts for tts in self.info.tts if tts.installed]
        if tts_installed:
            return tts_installed[0].name

        # wake-word-detection
        wake_installed = [wake for wake in self.info.wake if wake.installed]
        if wake_installed:
            return wake_installed[0].name

        # satellite
        satellite_installed: Satellite | None = None

        if (self.info.satellite is not None) and self.info.satellite.installed:
            satellite_installed = self.info.satellite

        if satellite_installed:
            return satellite_installed.name

        return None

    @classmethod
    async def create(cls, host: str, port: int) -> WyomingService | None:
        """Create a Wyoming service."""
        info = await load_wyoming_info(host, port)
        if info is None:
            return None

        return cls(host, port, info)


async def load_wyoming_info(
    host: str,
    port: int,
    retries: int = _INFO_RETRIES,
    retry_wait: float = _INFO_RETRY_WAIT,
    timeout: float = _INFO_TIMEOUT,
) -> Info | None:
    """Load info from Wyoming server."""
    wyoming_info: Info | None = None

    for _ in range(retries + 1):
        try:
            async with AsyncTcpClient(host, port) as client, asyncio.timeout(timeout):
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
                        break  # while

                if wyoming_info is not None:
                    break  # for
        except (TimeoutError, OSError, WyomingError):
            # Sleep and try again
            await asyncio.sleep(retry_wait)

    return wyoming_info
