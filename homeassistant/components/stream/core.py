"""Provides core stream functionality."""
from __future__ import annotations

import asyncio
from collections import deque
import datetime
from typing import TYPE_CHECKING

from aiohttp import web
import attr

from homeassistant.components.http.view import HomeAssistantView
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util.decorator import Registry

from .const import ATTR_STREAMS, DOMAIN, TARGET_SEGMENT_DURATION

if TYPE_CHECKING:
    from . import Stream

PROVIDERS = Registry()


@attr.s(slots=True)
class Part:
    """Represent a segment part."""

    duration: float = attr.ib()
    has_keyframe: bool = attr.ib()
    # video data (moof+mdat)
    data: bytes = attr.ib()


@attr.s(slots=True)
class Segment:
    """Represent a segment."""

    sequence: int = attr.ib(default=0)
    # the init of the mp4 the segment is based on
    init: bytes = attr.ib(default=None)
    duration: float = attr.ib(default=0)
    # For detecting discontinuities across stream restarts
    stream_id: int = attr.ib(default=0)
    parts: list[Part] = attr.ib(factory=list)
    start_time: datetime.datetime = attr.ib(factory=datetime.datetime.utcnow)

    @property
    def complete(self) -> bool:
        """Return whether the Segment is complete."""
        return self.duration > 0

    def get_bytes_without_init(self) -> bytes:
        """Return reconstructed data for all parts as bytes, without init."""
        return b"".join([part.data for part in self.parts])


class IdleTimer:
    """Invoke a callback after an inactivity timeout.

    The IdleTimer invokes the callback after some timeout has passed. The awake() method
    resets the internal alarm, extending the inactivity time.
    """

    def __init__(
        self, hass: HomeAssistant, timeout: int, idle_callback: CALLBACK_TYPE
    ) -> None:
        """Initialize IdleTimer."""
        self._hass = hass
        self._timeout = timeout
        self._callback = idle_callback
        self._unsub: CALLBACK_TYPE | None = None
        self.idle = False

    def start(self) -> None:
        """Start the idle timer if not already started."""
        self.idle = False
        if self._unsub is None:
            self._unsub = async_call_later(self._hass, self._timeout, self.fire)

    def awake(self) -> None:
        """Keep the idle time alive by resetting the timeout."""
        self.idle = False
        # Reset idle timeout
        self.clear()
        self._unsub = async_call_later(self._hass, self._timeout, self.fire)

    def clear(self) -> None:
        """Clear and disable the timer if it has not already fired."""
        if self._unsub is not None:
            self._unsub()

    def fire(self, _now: datetime.datetime) -> None:
        """Invoke the idle timeout callback, called when the alarm fires."""
        self.idle = True
        self._unsub = None
        self._callback()


class StreamOutput:
    """Represents a stream output."""

    def __init__(
        self,
        hass: HomeAssistant,
        idle_timer: IdleTimer,
        deque_maxlen: int | None = None,
    ) -> None:
        """Initialize a stream output."""
        self._hass = hass
        self.idle_timer = idle_timer
        self._event = asyncio.Event()
        self._segments: deque[Segment] = deque(maxlen=deque_maxlen)

    @property
    def name(self) -> str | None:
        """Return provider name."""
        return None

    @property
    def idle(self) -> bool:
        """Return True if the output is idle."""
        return self.idle_timer.idle

    @property
    def last_sequence(self) -> int:
        """Return the last sequence number without iterating."""
        if self._segments:
            return self._segments[-1].sequence
        return -1

    @property
    def sequences(self) -> list[int]:
        """Return current sequence from segments."""
        return [s.sequence for s in self._segments]

    @property
    def last_segment(self) -> Segment | None:
        """Return the last segment without iterating."""
        if self._segments:
            return self._segments[-1]
        return None

    @property
    def target_duration(self) -> float:
        """Return the max duration of any given segment in seconds."""
        if not (durations := [s.duration for s in self._segments if s.complete]):
            return TARGET_SEGMENT_DURATION
        return max(durations)

    def get_segment(self, sequence: int) -> Segment | None:
        """Retrieve a specific segment."""
        # Most hits will come in the most recent segments, so iterate reversed
        for segment in reversed(self._segments):
            if segment.sequence == sequence:
                return segment
        return None

    def get_segments(self) -> deque[Segment]:
        """Retrieve all segments."""
        return self._segments

    async def recv(self) -> bool:
        """Wait for and retrieve the latest segment."""
        await self._event.wait()
        return self.last_segment is not None

    def put(self, segment: Segment) -> None:
        """Store output."""
        self._hass.loop.call_soon_threadsafe(self._async_put, segment)

    @callback
    def _async_put(self, segment: Segment) -> None:
        """Store output from event loop."""
        # Start idle timeout when we start receiving data
        self.idle_timer.start()
        self._segments.append(segment)
        self._event.set()
        self._event.clear()

    def cleanup(self) -> None:
        """Handle cleanup."""
        self._event.set()
        self.idle_timer.clear()
        self._segments = deque(maxlen=self._segments.maxlen)


class StreamView(HomeAssistantView):
    """
    Base StreamView.

    For implementation of a new stream format, define `url` and `name`
    attributes, and implement `handle` method in a child class.
    """

    requires_auth = False
    platform = None

    async def get(
        self, request: web.Request, token: str, sequence: str = ""
    ) -> web.StreamResponse:
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

    async def handle(
        self, request: web.Request, stream: Stream, sequence: str
    ) -> web.StreamResponse:
        """Handle the stream request."""
        raise NotImplementedError()
