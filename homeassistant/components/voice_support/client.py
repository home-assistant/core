"""Talking to the Voice app, a server on the Supervisor's network.

``GET /info`` is how the pipeline knows whether to ask satellites for wake
word audio at all. The run itself is a websocket, in ``run.py``.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_VERSION, INFO_TIMEOUT, LOGGER, RUN_TIMEOUT
from .run import AudioRun, AudioRunRequest


@dataclass(frozen=True)
class AppInfo:
    """What the app says it is and what it can do."""

    name: str
    version: str
    api_version: int
    wake_words: dict[str, str | None] = field(default_factory=dict)
    """Normalized wake word id -> the phrase said, when it gave one."""

    max_run_ms: int = 0
    """The most audio it holds for one run. Nothing here enforces it; it is
    somewhere for a run cut short to be explained."""

    @staticmethod
    def from_json(data: dict[str, Any]) -> AppInfo:
        """Read an /info response."""
        return AppInfo(
            name=str(data.get("name") or "Voice"),
            version=str(data.get("version") or "unknown"),
            api_version=int(data.get("api_version") or 0),
            wake_words={
                normalize_wake_word(str(wake_word["id"])): wake_word.get("phrase")
                for wake_word in data.get("wake_words") or []
                if wake_word.get("id")
            },
            max_run_ms=int(data.get("max_run_ms") or 0),
        )


def normalize_wake_word(wake_word: str) -> str:
    """Treat "Okay Nabu", "okay-nabu" and "okay_nabu" as one wake word.

    Pipelines name a wake word by the phrase said and detectors by an id,
    and the difference between the two spellings has never meant anything.
    """
    lowered = wake_word.lower().replace("-", "_").replace(" ", "_")
    return "".join(c for c in lowered if c.isalnum() or c == "_")


class VoiceSupportClient:
    """The Voice app, as the pipeline's audio run provider."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        """Set up a client for the app at this address."""
        self.hass = hass
        self.url = f"http://{host}:{port}"
        self.info: AppInfo | None = None
        self._listeners: list[Callable[[], None]] = []

    @property
    def available(self) -> bool:
        """Whether the app answered and can verify anything right now."""
        return (self.info is not None) and bool(self.info.wake_words)

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Follow whether the app can verify, and return how to stop.

        Whether to ask a satellite for wake word audio is decided once, not
        per detection, so an app going away has to be noticed rather than
        discovered at the next one.
        """
        self._listeners.append(listener)

        @callback
        def _remove() -> None:
            self._listeners.remove(listener)

        return _remove

    async def async_update_info(self) -> AppInfo:
        """Ask the app what it is and what it can verify."""
        was_available = self.available
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"{self.url}/info", timeout=aiohttp.ClientTimeout(total=INFO_TIMEOUT)
            ) as response:
                response.raise_for_status()
                info = AppInfo.from_json(await response.json())
        except aiohttp.ClientError, TimeoutError, ValueError:
            self._async_set_info(None, was_available)
            raise

        if info.api_version != API_VERSION:
            LOGGER.warning(
                "%s speaks protocol version %s, not %s: nothing will be verified",
                info.name,
                info.api_version,
                API_VERSION,
            )
            info = AppInfo(info.name, info.version, info.api_version)

        self._async_set_info(info, was_available)
        LOGGER.debug(
            "%s %s verifies: %s",
            info.name,
            info.version,
            ", ".join(sorted(info.wake_words)) or "(nothing)",
        )
        return info

    @callback
    def _async_set_info(self, info: AppInfo | None, was_available: bool) -> None:
        """Keep what the app said, and say so if that changed."""
        self.info = info
        if self.available != was_available:
            for listener in list(self._listeners):
                listener()

    def supports_wake_word(self, wake_word_phrase: str) -> bool:
        """Whether the app can verify this wake word."""
        return (self.info is not None) and (
            normalize_wake_word(wake_word_phrase) in self.info.wake_words
        )

    async def async_start_run(self, request: AudioRunRequest) -> AudioRun | None:
        """Open a run with the app, or None to leave it out of this one."""
        if self.info is None:
            return None

        session = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(RUN_TIMEOUT):
                websocket = await session.ws_connect(f"{self.url}/run")
                await websocket.send_json(
                    {
                        "type": "run-start",
                        "satellite_id": request.satellite_id,
                        "wake_word_phrase": request.wake_word_phrase,
                        "wake_word_audio_ms": request.wake_word_audio_ms or 0,
                        "silence_seconds": request.silence_seconds,
                    }
                )
        except (aiohttp.ClientError, TimeoutError) as err:
            LOGGER.debug("Cannot reach the app (%s): running without it", err)
            return None

        return AudioRun(self.hass, websocket)
