"""Base class for Wyoming providers."""

from __future__ import annotations

import asyncio

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
        self.platforms = []

        if (self.info.satellite is not None) and self.info.satellite.installed:
            # Don't load platforms for satellite services, such as local wake
            # word detection.
            return

        if any(asr.installed for asr in info.asr):
            self.platforms.append(Platform.STT)
        if any(tts.installed for tts in info.tts):
            self.platforms.append(Platform.TTS)
        if any(wake.installed for wake in info.wake):
            self.platforms.append(Platform.WAKE_WORD)
        if any(intent.installed for intent in info.intent) or any(
            handle.installed for handle in info.handle
        ):
            self.platforms.append(Platform.CONVERSATION)

    def has_services(self) -> bool:
        """Return True if services are installed that Home Assistant can use."""
        return (
            any(asr for asr in self.info.asr if asr.installed)
            or any(tts for tts in self.info.tts if tts.installed)
            or any(wake for wake in self.info.wake if wake.installed)
            or any(intent for intent in self.info.intent if intent.installed)
            or any(handle for handle in self.info.handle if handle.installed)
            or ((self.info.satellite is not None) and self.info.satellite.installed)
        )

    def get_name(self) -> str | None:
        """Return name of first installed usable service."""

        # Wyoming satellite
        # Must be checked first because satellites may contain wake services, etc.
        if (self.info.satellite is not None) and self.info.satellite.installed:
            return self.info.satellite.name

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

        # intent recognition (text -> intent)
        intent_installed = [intent for intent in self.info.intent if intent.installed]
        if intent_installed:
            return intent_installed[0].name

        # intent handling (text -> text)
        handle_installed = [handle for handle in self.info.handle if handle.installed]
        if handle_installed:
            return handle_installed[0].name

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
                        raise WyomingError(  # noqa: TRY301
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
