"""Provides core stream functionality."""
from __future__ import annotations

import asyncio
from collections import deque
import io
from typing import TYPE_CHECKING, Any, Callable

from aiohttp import web
import attr

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util.decorator import Registry

from .const import ATTR_STREAMS, DOMAIN

if TYPE_CHECKING:
    import av.container
    import av.video

PROVIDERS = Registry()


@attr.s
class StreamBuffer:
    """Represent a segment."""

    segment: io.BytesIO = attr.ib()
    output: av.container.OutputContainer = attr.ib()
    vstream: av.video.VideoStream = attr.ib()
    astream = attr.ib(default=None)  # type=Optional[av.audio.AudioStream]


@attr.s
class Segment:
    """Represent a segment."""

    sequence: int = attr.ib()
    segment: io.BytesIO = attr.ib()
    duration: float = attr.ib()
    # For detecting discontinuities across stream restarts
    stream_id: int = attr.ib(default=0)


class IdleTimer:
    """Invoke a callback after an inactivity timeout.

    The IdleTimer invokes the callback after some timeout has passed. The awake() method
    resets the internal alarm, extending the inactivity time.
    """

    def __init__(
        self, hass: HomeAssistant, timeout: int, idle_callback: Callable[[], None]
    ):
        """Initialize IdleTimer."""
        self._hass = hass
        self._timeout = timeout
        self._callback = idle_callback
        self._unsub = None
        self.idle = False

    def start(self):
        """Start the idle timer if not already started."""
        self.idle = False
        if self._unsub is None:
            self._unsub = async_call_later(self._hass, self._timeout, self.fire)

    def awake(self):
        """Keep the idle time alive by resetting the timeout."""
        self.idle = False
        # Reset idle timeout
        self.clear()
        self._unsub = async_call_later(self._hass, self._timeout, self.fire)

    def clear(self):
        """Clear and disable the timer if it has not already fired."""
        if self._unsub is not None:
            self._unsub()

    def fire(self, _now=None):
        """Invoke the idle timeout callback, called when the alarm fires."""
        self.idle = True
        self._unsub = None
        self._callback()


class StreamOutput:
    """Represents a stream output."""

    def __init__(
        self, hass: HomeAssistant, idle_timer: IdleTimer, deque_maxlen: int = None
    ) -> None:
        """Initialize a stream output."""
        self._hass = hass
        self._idle_timer = idle_timer
        self._cursor = None
        self._event = asyncio.Event()
        self._segments = deque(maxlen=deque_maxlen)

    @property
    def name(self) -> str:
        """Return provider name."""
        return None

    @property
    def idle(self) -> bool:
        """Return True if the output is idle."""
        return self._idle_timer.idle

    @property
    def segments(self) -> list[int]:
        """Return current sequence from segments."""
        return [s.sequence for s in self._segments]

    @property
    def target_duration(self) -> int:
        """Return the max duration of any given segment in seconds."""
        segment_length = len(self._segments)
        if not segment_length:
            return 1
        durations = [s.duration for s in self._segments]
        return round(max(durations)) or 1

    def get_segment(self, sequence: int = None) -> Any:
        """Retrieve a specific segment, or the whole list."""
        self._idle_timer.awake()

        if not sequence:
            return self._segments

        for segment in self._segments:
            if segment.sequence == sequence:
                return segment
        return None

    async def recv(self) -> Segment:
        """Wait for and retrieve the latest segment."""
        last_segment = max(self.segments, default=0)
        if self._cursor is None or self._cursor <= last_segment:
            await self._event.wait()

        if not self._segments:
            return None

        segment = self.get_segment()[-1]
        self._cursor = segment.sequence
        return segment

    def put(self, segment: Segment) -> None:
        """Store output."""
        self._hass.loop.call_soon_threadsafe(self._async_put, segment)

    @callback
    def _async_put(self, segment: Segment) -> None:
        """Store output from event loop."""
        # Start idle timeout when we start receiving data
        self._idle_timer.start()
        self._segments.append(segment)
        self._event.set()
        self._event.clear()

    def cleanup(self):
        """Handle cleanup."""
        self._event.set()
        self._idle_timer.clear()
        self._segments = deque(maxlen=self._segments.maxlen)


class StreamView(HomeAssistantView):
    """
    Base StreamView.

    For implementation of a new stream format, define `url` and `name`
    attributes, and implement `handle` method in a child class.
    """

    requires_auth = False
    platform = None

    async def get(self, request, token, sequence=None):
        """Start a GET request."""
        hass = request.app["hass"]

        stream = next(
            (s for s in hass.data[DOMAIN][ATTR_STREAMS] if s.access_token == token),
            None,
        )

        if not stream:
            raise web.HTTPNotFound()

        # Start worker if not already started
        stream.start()

        return await self.handle(request, stream, sequence)

    async def handle(self, request, stream, sequence):
        """Handle the stream request."""
        raise NotImplementedError()
