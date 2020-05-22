"""Provides core stream functionality."""
import asyncio
from collections import deque
import io
from typing import Any, List

from aiohttp import web
import attr

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util.decorator import Registry

from .const import ATTR_STREAMS, DOMAIN

PROVIDERS = Registry()


@attr.s
class StreamBuffer:
    """Represent a segment."""

    segment = attr.ib(type=io.BytesIO)
    output = attr.ib()  # type=av.OutputContainer
    vstream = attr.ib()  # type=av.VideoStream
    astream = attr.ib(default=None)  # type=av.AudioStream


@attr.s
class Segment:
    """Represent a segment."""

    sequence = attr.ib(type=int)
    segment = attr.ib(type=io.BytesIO)
    duration = attr.ib(type=float)


class StreamOutput:
    """Represents a stream output."""

    num_segments = 3

    def __init__(self, stream, timeout: int = 300) -> None:
        """Initialize a stream output."""
        self.idle = False
        self.timeout = timeout
        self._stream = stream
        self._cursor = None
        self._event = asyncio.Event()
        self._segments = deque(maxlen=self.num_segments)
        self._unsub = None

    @property
    def name(self) -> str:
        """Return provider name."""
        return None

    @property
    def format(self) -> str:
        """Return container format."""
        return None

    @property
    def audio_codec(self) -> str:
        """Return desired audio codec."""
        return None

    @property
    def video_codec(self) -> str:
        """Return desired video codec."""
        return None

    @property
    def segments(self) -> List[int]:
        """Return current sequence from segments."""
        return [s.sequence for s in self._segments]

    @property
    def target_duration(self) -> int:
        """Return the average duration of the segments in seconds."""
        segment_length = len(self._segments)
        if not segment_length:
            return 0
        durations = [s.duration for s in self._segments]
        return round(sum(durations) // segment_length) or 1

    def get_segment(self, sequence: int = None) -> Any:
        """Retrieve a specific segment, or the whole list."""
        self.idle = False
        # Reset idle timeout
        if self._unsub is not None:
            self._unsub()
        self._unsub = async_call_later(self._stream.hass, self.timeout, self._timeout)

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

    @callback
    def put(self, segment: Segment) -> None:
        """Store output."""
        # Start idle timeout when we start receiving data
        if self._unsub is None:
            self._unsub = async_call_later(
                self._stream.hass, self.timeout, self._timeout
            )

        if segment is None:
            self._event.set()
            # Cleanup provider
            if self._unsub is not None:
                self._unsub()
            self.cleanup()
            return

        self._segments.append(segment)
        self._event.set()
        self._event.clear()

    @callback
    def _timeout(self, _now=None):
        """Handle stream timeout."""
        self._unsub = None
        if self._stream.keepalive:
            self.idle = True
            self._stream.check_idle()
        else:
            self.cleanup()

    def cleanup(self):
        """Handle cleanup."""
        self._segments = deque(maxlen=self.num_segments)
        self._stream.remove_provider(self)


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
            (
                s
                for s in hass.data[DOMAIN][ATTR_STREAMS].values()
                if s.access_token == token
            ),
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
