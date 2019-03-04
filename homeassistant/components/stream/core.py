"""Provides core stream functionality."""
import asyncio
import io
from typing import List, Any

import attr
from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, ATTR_STREAMS


@attr.s
class StreamBuffer:
    """Represent a segment."""

    segment = attr.ib(type=io.BytesIO)
    output = attr.ib()               # type=av.OutputContainer
    vstream = attr.ib()              # type=av.VideoStream
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

    def __init__(self) -> None:
        """Initialize a stream output."""
        self._cursor = None
        self._event = asyncio.Event()
        self._segments = []

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
        durations = [s.duration for s in self._segments]
        return round(sum(durations) // len(self._segments)) or 1

    def get_segment(self, sequence: int = None) -> Any:
        """Retrieve a specific segment, or the whole list."""
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

        segment = self._segments[-1]
        self._cursor = segment.sequence
        return segment

    async def put(self, segment: Segment) -> None:
        """Store output."""
        if segment is None:
            self._segments = []
            self._event.set()
            return

        self._segments.append(segment)
        if len(self._segments) > self.num_segments:
            self._segments = self._segments[-self.num_segments:]
        self._event.set()
        self._event.clear()


class StreamView(HomeAssistantView):
    """
    Base StreamView.

    For implementation of a new stream format, define `url` and `name`
    attributes, and implement `handle` method in a child class.
    """

    requires_auth = False
    platform = None

    def __init__(self):
        """Initialize a basic stream view."""
        self._unsub = None

    async def get(self, request, token, sequence=None):
        """Start a GET request."""
        hass = request.app['hass']

        stream = next((
            s for s in hass.data[DOMAIN][ATTR_STREAMS].values()
            if s.access_token == token), None)

        if not stream:
            raise web.HTTPNotFound()

        # Start worker if not already started
        stream.start()

        if self._unsub is not None:
            self._unsub()

        async def cleanup(_now):
            """Stop the stream."""
            stream.stop()
            self._unsub = None

        self._unsub = async_call_later(hass, 30, cleanup)

        return await self.handle(request, stream, sequence)

    async def handle(self, request, stream, sequence):
        """Handle the stream request."""
        raise NotImplementedError()
