"""Connect to the Voice app and read its capabilities."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterable, Awaitable, Callable
from dataclasses import dataclass, field
from json import JSONDecodeError
import logging
from typing import Any

import aiohttp
import probatio
from yarl import URL

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

API_VERSION = 1
INFO_TIMEOUT = 10
RUN_TIMEOUT = 1
SEND_TIMEOUT = 1
FINAL_EVENT_TIMEOUT = 1
WAKE_WORD_VERDICT_SECONDS = 2.0
BYTES_PER_MS = 32  # 16 kHz mono audio with 16-bit samples.

INFO_SCHEMA = probatio.Schema(
    {
        "name": str,
        "version": str,
        "api_version": int,
        "wake_words": [
            {
                "id": str,
                probatio.Optional("phrase"): probatio.Any(str, None),
            }
        ],
    },
    required=True,
    extra=probatio.ALLOW_EXTRA,
)

TIMESTAMP_SCHEMA = probatio.All(int, probatio.Range(min=0))
EVENT_SCHEMA = probatio.Schema({"type": str}, required=True, extra=probatio.ALLOW_EXTRA)
EVENT_SCHEMAS = {
    event_type: probatio.Schema(schema, required=True, extra=probatio.ALLOW_EXTRA)
    for event_type, schema in {
        "wake-word-end": {"wake_word_output": {"wake_word_audio_ms": TIMESTAMP_SCHEMA}},
        "wake-word-rejected": {
            "wake_word_output": {probatio.Optional("reason"): probatio.Any(str, None)}
        },
        "stt-vad-start": {"timestamp": TIMESTAMP_SCHEMA},
        "stt-vad-end": {"timestamp": TIMESTAMP_SCHEMA},
        "error": {"code": str, "message": str},
    }.items()
}

_LOGGER = logging.getLogger(__name__)


class InvalidResponseError(Exception):
    """The app returned malformed information."""


CLIENT_ERRORS = (aiohttp.ClientError, TimeoutError, InvalidResponseError)


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
        data = INFO_SCHEMA(data)
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
    """Metadata for an audio run."""

    satellite_id: str | None = None

    wake_word_phrase: str | None = None
    """None for runs started without a wake word."""

    wake_word_audio_ms: int | None = None
    """Milliseconds of audio preceding the wake word detection."""

    silence_seconds: float | None = None
    """None when end-of-command detection is disabled."""


@dataclass(frozen=True)
class WakeWordAccepted:
    """The app heard the wake word, ending at wake_word_audio_ms."""

    wake_word_audio_ms: int
    """The verified boundary replaces the satellite detection time."""


@dataclass(frozen=True)
class WakeWordRejected:
    """The app did not hear the wake word."""

    reason: str | None = None
    """In the app's own words, for logs only."""


class AudioRun:
    """Relay audio and read app events over a dedicated websocket."""

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
        """End of the command, measured from the first audio byte."""
        self.listening = True
        """Whether the app can still send events for this run."""

        self._websocket = websocket
        self._source = audio
        self._verifies_wake_word = verifies_wake_word
        self._chunks: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._error: Exception | None = None
        self._wake_word_known = asyncio.Event()
        self._finished = asyncio.Event()
        self._feeder = hass.async_create_background_task(
            self._async_feed(), "voice_support run audio", eager_start=True
        )
        self._reader = hass.async_create_background_task(
            self._async_read_answers(), "voice_support run answers", eager_start=True
        )

    async def async_wake_word(self) -> WakeWordAccepted | WakeWordRejected | None:
        """Return the verdict, or None if verification is unavailable or times out."""
        if not self._verifies_wake_word:
            return None
        try:
            async with asyncio.timeout(WAKE_WORD_VERDICT_SECONDS):
                await self._wake_word_known.wait()
        except TimeoutError:
            _LOGGER.debug("No wake word verdict within %ss", WAKE_WORD_VERDICT_SECONDS)
        return self.wake_word

    async def async_stream(self) -> AsyncGenerator[bytes]:
        """Stream audio through the command boundary, preserving source errors."""
        streamed_bytes = 0
        while (
            self.speech_ended_ms is None
            or streamed_bytes < self.speech_ended_ms * BYTES_PER_MS
        ):
            if (chunk := await self._chunks.get()) is None:
                break
            if not chunk:
                continue
            streamed_bytes += len(chunk)
            yield chunk
        if self._error is not None:
            raise self._error

    async def async_close(self) -> None:
        """Stop the audio relay and close the websocket."""
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
            try:
                async with asyncio.timeout(FINAL_EVENT_TIMEOUT):
                    await self._finished.wait()
            except TimeoutError:
                _LOGGER.debug("No final app event within %ss", FINAL_EVENT_TIMEOUT)
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
                    event = EVENT_SCHEMA(message.json())
                    if schema := EVENT_SCHEMAS.get(event["type"]):
                        event = schema(event)
                except (JSONDecodeError, probatio.Invalid) as err:
                    _LOGGER.warning("The app said something odd (%r)", err)
                    continue
                self._async_handle(event)
        except aiohttp.ClientError as err:
            _LOGGER.debug("The app went away mid-run (%r)", err)
        finally:
            self._async_stop_listening()

    @callback
    def _async_handle(self, event: dict[str, Any]) -> None:
        """Process an event from the app."""
        _LOGGER.debug("The app said %s", event)
        event_type = event["type"]

        if event_type == "wake-word-end":
            output = event["wake_word_output"]
            self.wake_word = WakeWordAccepted(output["wake_word_audio_ms"])
            self._wake_word_known.set()
        elif event_type == "wake-word-rejected":
            output = event["wake_word_output"]
            self.wake_word = WakeWordRejected(output.get("reason"))
            self._wake_word_known.set()
        elif event_type == "stt-vad-start":
            self.speech_started_ms = event["timestamp"]
        elif event_type == "stt-vad-end":
            self.speech_ended_ms = event["timestamp"]
            self._finished.set()
            # Wake the stream even when the source has no more audio to send.
            self._chunks.put_nowait(b"")
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
        self._finished.set()


class VoiceSupportClient:
    """The Voice app at one address and its capabilities."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        """Set up a client for the app at this address."""
        self.hass = hass
        self.url = URL.build(scheme="http", host=host, port=port)
        self.info: AppInfo | None = None

    async def async_update_info(self) -> AppInfo:
        """Ask the app what it is and what it can verify.

        Raises UnsupportedVersionError, besides CLIENT_ERRORS, for an app
        that cannot be used.
        """
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                self.url / "info", timeout=aiohttp.ClientTimeout(total=INFO_TIMEOUT)
            ) as response:
                response.raise_for_status()
                try:
                    data = await response.json()
                except JSONDecodeError as err:
                    raise InvalidResponseError(
                        "Invalid JSON from the Voice app"
                    ) from err
        except CLIENT_ERRORS:
            self.info = None
            raise

        try:
            info = AppInfo.from_json(data)
        except probatio.Invalid as err:
            self.info = None
            raise InvalidResponseError("Invalid info from the Voice app") from err

        if info.api_version != API_VERSION:
            self.info = None
            raise UnsupportedVersionError(info)

        self.info = info
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
            self.info = None
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
            self.info = None
            await websocket.close()
            return None
        except asyncio.CancelledError:
            await websocket.close()
            raise

        return AudioRun(self.hass, websocket, audio, verifies_wake_word)
