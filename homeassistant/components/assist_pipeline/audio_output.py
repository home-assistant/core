"""Streaming audio output for Assist pipelines."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from http import HTTPStatus
import logging
from secrets import token_urlsafe
from time import monotonic
from typing import Protocol

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

_LOGGER = logging.getLogger(__name__)

_MAX_BUFFERED_CHUNKS = 8
_OUTPUT_EXPIRATION_SECONDS = 300


class PipelineAudioOutputError(RuntimeError):
    """Error produced by a pipeline audio output."""

    def __init__(self, error: BaseException) -> None:
        """Initialize an output error."""
        self.error = error
        super().__init__(f"{type(error).__name__}: {error}")


class AudioOutputStream(Protocol):
    """Common audio stream interface used by pipeline response consumers."""

    token: str
    extension: str
    content_type: str

    @property
    def url(self) -> str:
        """Return the URL for the audio stream."""

    def async_stream_result(self) -> AsyncGenerator[bytes]:
        """Stream audio data."""


@dataclass(slots=True)
class PipelineAudioOutput:
    """Bounded, single-consumer audio stream produced by a pipeline."""

    token: str
    extension: str
    content_type: str
    _manager: PipelineAudioOutputManager = field(repr=False)
    _buffer_size: int = field(default=_MAX_BUFFERED_CHUNKS, repr=False)
    last_used: float = field(default_factory=monotonic, init=False)
    _consumer_started: bool = field(default=False, init=False, repr=False)
    _queue: asyncio.Queue[bytes] = field(init=False, repr=False)
    _terminal: asyncio.Future[BaseException | None] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize stream state."""
        self._queue = asyncio.Queue(maxsize=self._buffer_size)
        self._terminal = asyncio.get_running_loop().create_future()

    @property
    def url(self) -> str:
        """Return the URL for the audio stream."""
        return f"/api/assist_pipeline/audio/{self.token}"

    async def async_write(self, data: bytes) -> None:
        """Write an audio chunk, waiting while the bounded buffer is full."""
        if self._terminal.done():
            self._raise_terminal()

        put_task = asyncio.create_task(self._queue.put(data))
        try:
            await asyncio.wait(
                (put_task, self._terminal),
                return_when=asyncio.FIRST_COMPLETED,
            )
        except BaseException:
            if not put_task.done():
                put_task.cancel()
                with suppress(asyncio.CancelledError):
                    await put_task
            raise

        if self._terminal.done():
            if not put_task.done():
                put_task.cancel()
                with suppress(asyncio.CancelledError):
                    await put_task
            self._raise_terminal()

        await put_task

    @callback
    def async_close(self) -> None:
        """Close the stream successfully."""
        if not self._terminal.done():
            self._terminal.set_result(None)

    @callback
    def async_fail(self, err: BaseException) -> None:
        """Close the stream and propagate an error to its consumer."""
        if not self._terminal.done():
            if not isinstance(err, PipelineAudioOutputError):
                err = PipelineAudioOutputError(err)
            self._terminal.set_result(err)

    async def async_stream_result(self) -> AsyncGenerator[bytes]:
        """Stream audio chunks to the single consumer."""
        if self._consumer_started:
            raise RuntimeError("Pipeline audio output already has a consumer")
        self._consumer_started = True
        self.last_used = monotonic()

        try:
            while True:
                if self._terminal.done():
                    terminal_error = self._terminal.result()
                    if terminal_error is not None:
                        raise terminal_error
                    if self._queue.empty():
                        return

                try:
                    data = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    get_task = asyncio.create_task(self._queue.get())
                    try:
                        await asyncio.wait(
                            (get_task, self._terminal),
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                    except BaseException:
                        if not get_task.done():
                            get_task.cancel()
                            with suppress(asyncio.CancelledError):
                                await get_task
                        raise

                    if self._terminal.done() and self._terminal.result() is not None:
                        if not get_task.done():
                            get_task.cancel()
                            with suppress(asyncio.CancelledError):
                                await get_task
                        raise self._terminal.result() from None  # type: ignore[misc]

                    if not get_task.done():
                        get_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await get_task
                        continue
                    data = get_task.result()

                self.last_used = monotonic()
                yield data
        finally:
            if not self._terminal.done():
                self.async_fail(
                    RuntimeError("Pipeline audio output consumer stopped early")
                )

    def _raise_terminal(self) -> None:
        """Raise the terminal stream state."""
        terminal_error = self._terminal.result()
        if terminal_error is not None:
            raise terminal_error
        raise RuntimeError("Pipeline audio output is closed")


class PipelineAudioOutputManager:
    """Manage short-lived pipeline audio outputs."""

    def __init__(
        self,
        hass: HomeAssistant,
        expiration_seconds: float = _OUTPUT_EXPIRATION_SECONDS,
    ) -> None:
        """Initialize the output manager."""
        self._hass = hass
        self._expiration_seconds = expiration_seconds
        self._outputs: dict[str, PipelineAudioOutput] = {}
        self._unsub_cleanup: CALLBACK_TYPE | None = None
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_on_hass_stop)

    @callback
    def async_create(
        self,
        extension: str,
        content_type: str,
        *,
        buffer_size: int = _MAX_BUFFERED_CHUNKS,
    ) -> PipelineAudioOutput:
        """Create a pipeline audio output."""
        if not extension or not extension.isalnum():
            raise ValueError("extension must contain only letters and numbers")
        if buffer_size < 1:
            raise ValueError("buffer_size must be at least 1")

        token = f"{token_urlsafe(16)}.{extension}"
        output = PipelineAudioOutput(
            token=token,
            extension=extension,
            content_type=content_type,
            _manager=self,
            _buffer_size=buffer_size,
        )
        self._outputs[token] = output
        self._schedule_cleanup()
        return output

    @callback
    def async_get(self, token: str) -> PipelineAudioOutput | None:
        """Get an output by token."""
        if output := self._outputs.get(token):
            output.last_used = monotonic()
            return output
        return None

    @callback
    def _schedule_cleanup(self) -> None:
        """Schedule cleanup of expired outputs."""
        if self._unsub_cleanup is None:
            self._unsub_cleanup = async_call_later(
                self._hass,
                self._expiration_seconds + 1,
                self._async_cleanup,
            )

    @callback
    def _async_cleanup(self, _now: datetime) -> None:
        """Remove and fail expired outputs."""
        self._unsub_cleanup = None
        now = monotonic()
        for token, output in list(self._outputs.items()):
            if output.last_used + self._expiration_seconds < now:
                output.async_fail(TimeoutError("Pipeline audio output expired"))
                del self._outputs[token]

        if self._outputs:
            self._schedule_cleanup()

    @callback
    def _async_on_hass_stop(self, _event: Event) -> None:
        """Stop cleanup and terminate outputs."""
        if self._unsub_cleanup is not None:
            self._unsub_cleanup()
            self._unsub_cleanup = None
        for output in self._outputs.values():
            output.async_fail(RuntimeError("Home Assistant is stopping"))
        self._outputs.clear()


class PipelineAudioOutputView(HomeAssistantView):
    """Serve an Assist pipeline audio output."""

    requires_auth = False
    url = "/api/assist_pipeline/audio/{token}"
    name = "api:assist_pipeline:audio"

    def __init__(self, manager: PipelineAudioOutputManager) -> None:
        """Initialize the view."""
        self._manager = manager

    async def head(self, request: web.Request, token: str) -> web.StreamResponse:
        """Return metadata for an available audio output."""
        if (output := self._manager.async_get(token)) is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        return web.Response(content_type=output.content_type)

    async def get(self, request: web.Request, token: str) -> web.StreamResponse:
        """Stream an available audio output."""
        if (output := self._manager.async_get(token)) is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        response: web.StreamResponse | None = None
        try:
            async for data in output.async_stream_result():
                if response is None:
                    response = web.StreamResponse()
                    response.content_type = output.content_type
                    await response.prepare(request)
                await response.write(data)
        except Exception as err:
            _LOGGER.error("Error streaming Assist pipeline audio: %s", err)
            if response is not None:
                raise

        if response is None:
            return web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)

        await response.write_eof()
        return response
