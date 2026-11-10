"""The Voice app's protocol: what it can do, and runs opened with it."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterable, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

import aiohttp
from yarl import URL

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

API_VERSION = 1
INFO_TIMEOUT = 10
RUN_TIMEOUT = 1
"""Opening or closing a run sits between the wake word and the command."""
SEND_TIMEOUT = 1
"""An app that stops taking audio has stopped listening."""
CONNECT_ERRORS = (
    aiohttp.ClientError,
    TimeoutError,
    AttributeError,
    KeyError,
    TypeError,
    ValueError,
)
"""What reading the app's info may raise, a malformed answer included."""
INFO_REFRESH_INTERVAL = timedelta(minutes=5)
WAKE_WORD_VERDICT_SECONDS = 2.0
"""How long a run may take over a wake word before it is accepted anyway."""

_LOGGER = logging.getLogger(__name__)


class UnsupportedVersionError(Exception):
    """The app speaks a protocol version this Home Assistant does not."""

    def __init__(self, info: AppInfo) -> None:
        """Initialize the error."""
        super().__init__(
            f"{info.name} {info.version} speaks protocol version "
            f"{info.api_version}, not {API_VERSION}"
        )
        self.info = info


@dataclass(frozen=True)
class AppInfo:
    """What the app says it is and what it can do."""

    name: str
    version: str
    api_version: int
    wake_words: dict[str, str | None] = field(default_factory=dict)
    """Normalized wake word id -> the phrase said, when it gave one."""

    @staticmethod
    def from_json(data: dict[str, Any]) -> AppInfo:
        """Read an /info response."""
        return AppInfo(
            name=data["name"],
            version=data["version"],
            api_version=data["api_version"],
            wake_words={
                normalize_wake_word(wake_word["id"]): wake_word.get("phrase")
                for wake_word in data["wake_words"]
            },
        )


def normalize_wake_word(wake_word: str) -> str:
    """Treat "Okay Nabu", "okay-nabu" and "okay_nabu" as one wake word."""
    lowered = wake_word.lower().replace("-", "_").replace(" ", "_")
    return "".join(c for c in lowered if c.isalnum() or c == "_")


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
    """The app heard the wake word, ending at wake_word_audio_ms."""

    wake_word_audio_ms: int
    """Replaces the satellite's own, which is only where a threshold was
    crossed: early for some speakers, late for others."""


@dataclass(frozen=True)
class WakeWordRejected:
    """The app did not hear the wake word."""

    reason: str | None = None
    """In the app's own words, for logs only."""


def _ms(value: Any) -> int:
    """A point in the run's audio, as the app must give it."""
    if isinstance(value, bool) or (not isinstance(value, int)) or (value < 0):
        raise ValueError(f"not a point in the audio: {value!r}")
    return value


class AudioRun:
    """One run, open with the app.

    A task of its own relays the audio, so nothing waiting on the app ever
    cancels the satellite's stream. Each run has a connection of its own.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        websocket: aiohttp.ClientWebSocketResponse,
        audio: AsyncIterable[bytes],
        verifies_wake_word: bool,
    ) -> None:
        """Start relaying the audio and reading the app's answers."""
        self.wake_word: WakeWordAccepted | WakeWordRejected | None = None
        self.speech_started_ms: int | None = None
        """Milliseconds from the first audio of the run."""
        self.speech_ended_ms: int | None = None
        """Where the command is over, and so is the audio speech-to-text
        should hear."""
        self.listening = True
        """False once the app has stopped having opinions, whether it
        finished or went away."""

        self._websocket = websocket
        self._source = audio
        self._verifies_wake_word = verifies_wake_word
        self._chunks: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._error: Exception | None = None
        self._wake_word_known = asyncio.Event()
        self._feeder = hass.async_create_background_task(
            self._async_feed(), "voice_support run audio", eager_start=True
        )
        self._reader = hass.async_create_background_task(
            self._async_read_answers(), "voice_support run answers", eager_start=True
        )

    async def async_wake_word(self) -> WakeWordAccepted | WakeWordRejected | None:
        """Wait for the app's verdict on the wake word.

        None when the app has no say: it does not know this wake word, it
        stopped without answering, or it took too long.
        """
        if not self._verifies_wake_word:
            return None
        try:
            async with asyncio.timeout(WAKE_WORD_VERDICT_SECONDS):
                await self._wake_word_known.wait()
        except TimeoutError:
            _LOGGER.debug("No wake word verdict within %ss", WAKE_WORD_VERDICT_SECONDS)
        return self.wake_word

    async def async_stream(self) -> AsyncGenerator[bytes]:
        """The run's audio as it came in, raising whatever the source raised."""
        while (chunk := await self._chunks.get()) is not None:
            yield chunk
        if self._error is not None:
            raise self._error

    async def async_close(self) -> None:
        """Let the run go, however it ended."""
        self._feeder.cancel()
        self._reader.cancel()
        await self._websocket.close()

    async def _async_feed(self) -> None:
        """Relay the audio to the app and on to whoever streams the run."""
        try:
            async for chunk in self._source:
                self._chunks.put_nowait(chunk)
                await self._async_send(self._websocket.send_bytes, chunk)
            await self._async_send(self._websocket.send_json, {"type": "audio-end"})
        except Exception as err:  # noqa: BLE001
            self._error = err
        finally:
            self._chunks.put_nowait(None)

    async def _async_send[T](
        self, send: Callable[[T], Awaitable[None]], message: T
    ) -> None:
        if (not self.listening) or self._websocket.closed:
            return
        try:
            async with asyncio.timeout(SEND_TIMEOUT):
                await send(message)
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("The app went away mid-run (%r)", err)
            self._async_stop_listening()

    async def _async_read_answers(self) -> None:
        """Read the app's answers until it has no more."""
        try:
            async for message in self._websocket:
                if message.type != aiohttp.WSMsgType.TEXT:
                    continue
                try:
                    self._async_handle(message.json())
                except (AttributeError, KeyError, TypeError, ValueError) as err:
                    _LOGGER.warning("The app said something odd (%r)", err)
        except aiohttp.ClientError as err:
            _LOGGER.debug("The app went away mid-run (%r)", err)
        finally:
            self._async_stop_listening()

    @callback
    def _async_handle(self, event: dict[str, Any]) -> None:
        """Keep what one of the app's messages says."""
        _LOGGER.debug("The app said %s", event)
        event_type = event["type"]

        if event_type == "wake-word-end":
            output = event["wake_word_output"]
            self.wake_word = WakeWordAccepted(_ms(output["wake_word_audio_ms"]))
            self._wake_word_known.set()
        elif event_type == "wake-word-rejected":
            output = event["wake_word_output"]
            self.wake_word = WakeWordRejected(output.get("reason"))
            self._wake_word_known.set()
        elif event_type == "stt-vad-start":
            self.speech_started_ms = _ms(event["timestamp"])
        elif event_type == "stt-vad-end":
            self.speech_ended_ms = _ms(event["timestamp"])
        elif event_type == "error":
            _LOGGER.warning(
                "The app could not handle the run (%s): %s",
                event["code"],
                event["message"],
            )
            self._async_stop_listening()
        else:
            _LOGGER.debug("Ignoring %s from the app", event_type)

    @callback
    def _async_stop_listening(self) -> None:
        """Stop expecting anything more from the app, releasing any waiter."""
        self.listening = False
        self._wake_word_known.set()


class VoiceSupportClient:
    """The Voice app at one address: what it can do, and runs opened with it."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        """Set up a client for the app at this address."""
        self.hass = hass
        self.url = URL.build(scheme="http", host=host, port=port)
        self.info: AppInfo | None = None
        self._stop_refresh: CALLBACK_TYPE | None = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._listeners: list[CALLBACK_TYPE] = []

    async def async_connect(self) -> None:
        """Ask the app what it is, and keep asking now and then.

        An app that is updated, or that goes away and comes back, is only
        noticed by asking again.
        """
        await self.async_update_info()
        self._stop_refresh = async_track_time_interval(
            self.hass, self._async_refresh_info, INFO_REFRESH_INTERVAL
        )

    @callback
    def async_close(self) -> None:
        """Stop following the app."""
        if self._stop_refresh is not None:
            self._stop_refresh()
            self._stop_refresh = None
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            self._refresh_task = None

    @callback
    def _async_schedule_refresh(self) -> None:
        """Ask the app again soon, so one that is gone stops being tried."""
        if (self._refresh_task is not None) and (not self._refresh_task.done()):
            return
        self._refresh_task = self.hass.async_create_background_task(
            self._async_refresh_info(), "voice_support info refresh"
        )

    async def _async_refresh_info(self, _now: datetime | None = None) -> None:
        was_usable = self.info is not None
        try:
            await self.async_update_info()
        except CONNECT_ERRORS as err:
            _LOGGER.debug("Cannot read the app at %s (%r)", self.url, err)
        except UnsupportedVersionError as err:
            # Once, when an update changed it; not every refresh after
            if was_usable:
                _LOGGER.warning("%s: nothing will be verified", err)

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Follow what the app can verify, and return how to stop.

        Whether to ask a satellite for wake word audio is decided once, not
        per detection, so a change in the app's models has to be announced
        rather than discovered at the next one.
        """
        self._listeners.append(listener)

        @callback
        def _remove() -> None:
            self._listeners.remove(listener)

        return _remove

    @callback
    def _async_wake_words_changed(self, before: AppInfo | None) -> None:
        """Tell anyone following, if what can be verified actually moved."""
        was = set(before.wake_words) if before is not None else set()
        now = set(self.info.wake_words) if self.info is not None else set()
        if was == now:
            return
        for listener in list(self._listeners):
            listener()

    async def async_update_info(self) -> AppInfo:
        """Ask the app what it is and what it can verify.

        Raises UnsupportedVersionError, besides CONNECT_ERRORS, for an app
        that cannot be used.
        """
        before = self.info
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                self.url / "info", timeout=aiohttp.ClientTimeout(total=INFO_TIMEOUT)
            ) as response:
                response.raise_for_status()
                info = AppInfo.from_json(await response.json())
        except CONNECT_ERRORS:
            self.info = None
            self._async_wake_words_changed(before)
            raise

        if info.api_version != API_VERSION:
            self.info = None
            self._async_wake_words_changed(before)
            raise UnsupportedVersionError(info)

        self.info = info
        self._async_wake_words_changed(before)
        _LOGGER.debug(
            "%s %s verifies: %s",
            info.name,
            info.version,
            ", ".join(sorted(info.wake_words)) or "(nothing)",
        )
        return info

    def supports_wake_word(self, wake_word_phrase: str) -> bool:
        """Whether the app can verify this wake word."""
        return (self.info is not None) and (
            normalize_wake_word(wake_word_phrase) in self.info.wake_words
        )

    async def async_start_run(
        self, request: AudioRunRequest, audio: AsyncIterable[bytes]
    ) -> AudioRun | None:
        """Open a run with the app, or None if it has nothing to do there."""
        if self.info is None:
            return None

        # Only a wake word that is in the audio can be verified
        verifies_wake_word = (
            (request.wake_word_phrase is not None)
            and (request.wake_word_audio_ms is not None)
            and self.supports_wake_word(request.wake_word_phrase)
        )
        if (not verifies_wake_word) and (request.silence_seconds is None):
            return None

        session = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(RUN_TIMEOUT):
                websocket = await session.ws_connect(
                    self.url / "run",
                    timeout=aiohttp.ClientWSTimeout(ws_close=RUN_TIMEOUT),
                )
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("Cannot reach the app (%r): running without it", err)
            self._async_schedule_refresh()
            return None

        try:
            async with asyncio.timeout(RUN_TIMEOUT):
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
            _LOGGER.debug("The app would not take a run (%r): running without it", err)
            self._async_schedule_refresh()
            await websocket.close()
            return None

        return AudioRun(self.hass, websocket, audio, verifies_wake_word)
