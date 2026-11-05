"""One run, watched by the app.

Audio goes in from the satellite's first chunk to its last, and back comes
the wake word's verdict and where the command begins and ends. Answers
arrive on their own schedule, so a task of its own reads them and the
pipeline reads the attributes below rather than asking.

Nothing here refuses a wake word or ends a command on the app's behalf: an
app that is down, slow or confused says nothing, and the run goes on.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant, callback

from .const import LOGGER


@dataclass(frozen=True)
class AudioRunRequest:
    """What Home Assistant knows about a run before any of it is heard."""

    satellite_id: str | None = None

    wake_word_phrase: str | None = None
    """None when the run did not start at a wake word: a button press, or a
    stream that starts at speech-to-text."""

    wake_word_audio_ms: int | None = None
    """The detection sits at the end of this much of the audio."""

    silence_seconds: float | None = None
    """The person's voice activity sensitivity, resolved to seconds. None
    when end-of-command detection is off."""


@dataclass(frozen=True)
class WakeWordAccepted:
    """That was the wake word, and this is where it ends."""

    wake_word_audio_ms: int
    """Replaces the satellite's own, which is only where a threshold was
    crossed: early for some speakers, late for others."""


@dataclass(frozen=True)
class WakeWordRejected:
    """That was not the wake word. The run ends here."""

    reason: str | None = None
    """In the app's own words, for logs only."""


@dataclass(frozen=True)
class SpeechStarted:
    """The person began speaking the command."""

    timestamp_ms: int
    """Milliseconds from the first audio of the run."""


@dataclass(frozen=True)
class SpeechEnded:
    """The command is over, and so is the audio speech-to-text should hear."""

    timestamp_ms: int


type AudioRunEvent = WakeWordAccepted | WakeWordRejected | SpeechStarted | SpeechEnded


class AudioRun:
    """One run, open with the app over a websocket of its own.

    Audio frames have nowhere to carry a run id, so a shared connection
    would mean tagging every chunk of every satellite's audio -- and a run
    that wedges would take the others with it.
    """

    def __init__(
        self, hass: HomeAssistant, websocket: aiohttp.ClientWebSocketResponse
    ) -> None:
        """Watch a run over this connection."""
        self.wake_word: WakeWordAccepted | WakeWordRejected | None = None
        self.speech_started_ms: int | None = None
        self.speech_ended_ms: int | None = None
        self.listening = True
        """False once the app has stopped having opinions, whether it
        finished or went away."""

        self._websocket = websocket
        self._wake_word_known = asyncio.Event()
        self._reader = hass.async_create_background_task(
            self._async_read(), "voice_support run", eager_start=True
        )

    async def async_wake_word(
        self, timeout: float
    ) -> WakeWordAccepted | WakeWordRejected | None:
        """Wait for the verdict; None means there will not be one.

        The person is standing there with the wake word already spoken, so
        running out of time accepts the detection.
        """
        try:
            async with asyncio.timeout(timeout):
                await self._wake_word_known.wait()
        except TimeoutError:
            return None
        return self.wake_word

    async def async_write(self, audio: bytes) -> None:
        """Send the next of the run's audio, as 16 kHz 16-bit mono PCM.

        Never waits on anything the app is thinking about.
        """
        if not self._websocket.closed:
            await self._websocket.send_bytes(audio)

    async def async_end_audio(self) -> None:
        """Tell the app the satellite has stopped streaming."""
        if not self._websocket.closed:
            await self._websocket.send_json({"type": "audio-end"})

    async def async_close(self) -> None:
        """Let the run go, however it ended."""
        self._reader.cancel()
        await self._websocket.close()

    # ------------------------------------------------------------------

    async def _async_read(self) -> None:
        """Take what the app says until it stops saying anything."""
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
            # Finished or fallen over, nothing more is coming.
            self.stop_listening()

    @callback
    def _async_handle(self, event: dict[str, Any]) -> None:
        """Turn one of the app's messages into something the pipeline reads."""
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
        """Keep one event, and wake anything waiting on it."""
        if isinstance(event, (WakeWordAccepted, WakeWordRejected)):
            self.wake_word = event
            self._wake_word_known.set()
        elif isinstance(event, SpeechStarted):
            self.speech_started_ms = event.timestamp_ms
        else:
            self.speech_ended_ms = event.timestamp_ms

    @callback
    def stop_listening(self) -> None:
        """Stop expecting anything more from the app about this run.

        The reader calls this when the app finishes or falls over, the
        pipeline when it cannot reach the app at all. Either way it falls
        back to its own answers.
        """
        self.listening = False
        self._wake_word_known.set()
