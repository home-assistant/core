"""A run with the Voice app."""

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant, callback

from .const import LOGGER


@dataclass(frozen=True)
class AudioRunRequest:
    """Details of a run sent to the app."""

    satellite_id: str | None = None
    wake_word_phrase: str | None = None
    wake_word_audio_ms: int | None = None
    silence_seconds: float | None = None


@dataclass(frozen=True)
class WakeWordAccepted:
    """The app accepted the wake word."""

    wake_word_audio_ms: int


@dataclass(frozen=True)
class WakeWordRejected:
    """The app rejected the wake word."""

    reason: str | None = None


@dataclass(frozen=True)
class SpeechStarted:
    """The command started."""

    timestamp_ms: int


@dataclass(frozen=True)
class SpeechEnded:
    """The command ended."""

    timestamp_ms: int


type AudioRunEvent = WakeWordAccepted | WakeWordRejected | SpeechStarted | SpeechEnded


class AudioRun:
    """A run with the app, over its own websocket."""

    def __init__(
        self, hass: HomeAssistant, websocket: aiohttp.ClientWebSocketResponse
    ) -> None:
        """Initialize the run."""
        self.wake_word: WakeWordAccepted | WakeWordRejected | None = None
        self.speech_started_ms: int | None = None
        self.speech_ended_ms: int | None = None
        self.listening = True

        self._websocket = websocket
        self._wake_word_known = asyncio.Event()
        self._reader = hass.async_create_background_task(
            self._async_read(), "voice_support run", eager_start=True
        )

    async def async_wake_word(
        self, timeout: float
    ) -> WakeWordAccepted | WakeWordRejected | None:
        """Wait for the app's wake word verdict, or None if there is none."""
        try:
            async with asyncio.timeout(timeout):
                await self._wake_word_known.wait()
        except TimeoutError:
            return None
        return self.wake_word

    async def async_write(self, audio: bytes) -> None:
        """Send 16 kHz 16-bit mono audio to the app."""
        if not self._websocket.closed:
            await self._websocket.send_bytes(audio)

    async def async_end_audio(self) -> None:
        """Tell the app the audio has ended."""
        if not self._websocket.closed:
            await self._websocket.send_json({"type": "audio-end"})

    async def async_close(self) -> None:
        """Close the run."""
        self._reader.cancel()
        await self._websocket.close()

    async def _async_read(self) -> None:
        """Read events from the app."""
        try:
            async for message in self._websocket:
                if message.type != aiohttp.WSMsgType.TEXT:
                    continue
                try:
                    self._async_handle(message.json())
                except (KeyError, TypeError, ValueError) as err:
                    LOGGER.warning("The app said something odd (%s)", err)
        except aiohttp.ClientError as err:
            LOGGER.debug("The app went away mid-run (%s)", err)
        finally:
            self.stop_listening()

    @callback
    def _async_handle(self, event: dict[str, Any]) -> None:
        """Handle an event from the app."""
        event_type = event.get("type")
        output = event.get("wake_word_output") or {}

        if event_type == "wake-word-end":
            self._async_event(WakeWordAccepted(int(output["wake_word_audio_ms"])))
        elif event_type == "wake-word-rejected":
            self._async_event(WakeWordRejected(output.get("reason")))
        elif event_type == "stt-vad-start":
            self._async_event(SpeechStarted(int(event["timestamp"])))
        elif event_type == "stt-vad-end":
            self._async_event(SpeechEnded(int(event["timestamp"])))
        elif event_type == "error":
            LOGGER.warning(
                "The app could not handle the run (%s): %s",
                event.get("code"),
                event.get("message"),
            )
        else:
            LOGGER.debug("Ignoring %s from the app", event_type)

    @callback
    def _async_event(self, event: AudioRunEvent) -> None:
        """Store an event from the app."""
        if isinstance(event, (WakeWordAccepted, WakeWordRejected)):
            self.wake_word = event
            self._wake_word_known.set()
        elif isinstance(event, SpeechStarted):
            self.speech_started_ms = event.timestamp_ms
        else:
            self.speech_ended_ms = event.timestamp_ms

    @callback
    def stop_listening(self) -> None:
        """Stop waiting for events from the app."""
        self.listening = False
        self._wake_word_known.set()
