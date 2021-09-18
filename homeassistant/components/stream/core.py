"""Provides core stream functionality."""
from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Iterable
import datetime
from typing import TYPE_CHECKING

from aiohttp import web
import async_timeout
import attr

from homeassistant.components.http.view import HomeAssistantView
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util.decorator import Registry

from .const import ATTR_STREAMS, DOMAIN

if TYPE_CHECKING:
    from . import Stream

PROVIDERS = Registry()


@attr.s(slots=True)
class StreamSettings:
    """Stream settings."""

    ll_hls: bool = attr.ib()
    min_segment_duration: float = attr.ib()
    part_target_duration: float = attr.ib()
    hls_advance_part_limit: int = attr.ib()
    hls_part_timeout: float = attr.ib()


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

    sequence: int = attr.ib()
    # the init of the mp4 the segment is based on
    init: bytes = attr.ib()
    # For detecting discontinuities across stream restarts
    stream_id: int = attr.ib()
    start_time: datetime.datetime = attr.ib()
    _stream_outputs: Iterable[StreamOutput] = attr.ib()
    duration: float = attr.ib(default=0)
    parts: list[Part] = attr.ib(factory=list)
    # Store text of this segment's hls playlist for reuse
    # Use list[str] for easy appends
    hls_playlist_template: list[str] = attr.ib(factory=list)
    hls_playlist_parts: list[str] = attr.ib(factory=list)
    # Number of playlist parts rendered so far
    hls_num_parts_rendered: int = attr.ib(default=0)
    # Set to true when all the parts are rendered
    hls_playlist_complete: bool = attr.ib(default=False)

    def __attrs_post_init__(self) -> None:
        """Run after init."""
        for output in self._stream_outputs:
            output.put(self)

    @property
    def complete(self) -> bool:
        """Return whether the Segment is complete."""
        return self.duration > 0

    @property
    def data_size_with_init(self) -> int:
        """Return the size of all part data + init in bytes."""
        return len(self.init) + self.data_size

    @property
    def data_size(self) -> int:
        """Return the size of all part data without init in bytes."""
        return sum(len(part.data) for part in self.parts)

    @callback
    def async_add_part(
        self,
        part: Part,
        duration: float,
    ) -> None:
        """Add a part to the Segment.

        Duration is non zero only for the last part.
        """
        self.parts.append(part)
        self.duration = duration
        for output in self._stream_outputs:
            output.part_put()

    def get_data(self) -> bytes:
        """Return reconstructed data for all parts as bytes, without init."""
        return b"".join([part.data for part in self.parts])

    def _render_hls_template(self, last_stream_id: int, render_parts: bool) -> str:
        """Render the HLS playlist section for the Segment.

        The Segment may still be in progress.
        This method stores intermediate data in hls_playlist_parts, hls_num_parts_rendered,
        and hls_playlist_complete to avoid redoing work on subsequent calls.
        """
        if self.hls_playlist_complete:
            return self.hls_playlist_template[0]
        if not self.hls_playlist_template:
            # This is a placeholder where the rendered parts will be inserted
            self.hls_playlist_template.append("{}")
        if render_parts:
            for part_num, part in enumerate(
                self.parts[self.hls_num_parts_rendered :], self.hls_num_parts_rendered
            ):
                self.hls_playlist_parts.append(
                    f"#EXT-X-PART:DURATION={part.duration:.3f},URI="
                    f'"./segment/{self.sequence}.{part_num}.m4s"{",INDEPENDENT=YES" if part.has_keyframe else ""}'
                )
        if self.complete:
            # Construct the final playlist_template. The placeholder will share a line with
            # the first element to avoid an extra newline when we don't render any parts.
            # Append an empty string to create a trailing newline when we do render parts
            self.hls_playlist_parts.append("")
            self.hls_playlist_template = []
            # Logically EXT-X-DISCONTINUITY would make sense above the parts, but Apple's
            # media stream validator seems to only want it before the segment
            if last_stream_id != self.stream_id:
                self.hls_playlist_template.append("#EXT-X-DISCONTINUITY")
            # Add the remaining segment metadata
            self.hls_playlist_template.extend(
                [
                    "#EXT-X-PROGRAM-DATE-TIME:"
                    + self.start_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
                    + "Z",
                    f"#EXTINF:{self.duration:.3f},\n./segment/{self.sequence}.m4s",
                ]
            )
            # The placeholder now goes on the same line as the first element
            self.hls_playlist_template[0] = "{}" + self.hls_playlist_template[0]

        # Store intermediate playlist data in member variables for reuse
        self.hls_playlist_template = ["\n".join(self.hls_playlist_template)]
        # lstrip discards extra preceding newline in case first render was empty
        self.hls_playlist_parts = ["\n".join(self.hls_playlist_parts).lstrip()]
        self.hls_num_parts_rendered = len(self.parts)
        self.hls_playlist_complete = self.complete

        return self.hls_playlist_template[0]

    def render_hls(
        self, last_stream_id: int, render_parts: bool, add_hint: bool
    ) -> str:
        """Render the HLS playlist section for the Segment including a hint if requested."""
        playlist_template = self._render_hls_template(last_stream_id, render_parts)
        playlist = playlist_template.format(
            self.hls_playlist_parts[0] if render_parts else ""
        )
        if not add_hint:
            return playlist
        # Preload hints help save round trips by informing the client about the next part.
        # The next part will usually be in this segment but will be first part of the next
        # segment if this segment is already complete.
        if self.complete:  # Next part belongs to next segment
            sequence = self.sequence + 1
            part_num = 0
        else:  # Next part is in the same segment
            sequence = self.sequence
            part_num = len(self.parts)
        hint = (
            f'#EXT-X-PRELOAD-HINT:TYPE=PART,URI="./segment/{sequence}.{part_num}.m4s"'
        )
        return (playlist + "\n" + hint) if playlist else hint


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
        self._part_event = asyncio.Event()
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

    async def part_recv(self, timeout: float | None = None) -> bool:
        """Wait for an event signalling the latest part segment."""
        try:
            async with async_timeout.timeout(timeout):
                await self._part_event.wait()
        except asyncio.TimeoutError:
            return False
        return True

    def part_put(self) -> None:
        """Set event signalling the latest part segment."""
        # Start idle timeout when we start receiving data
        self._part_event.set()
        self._part_event.clear()

    async def recv(self) -> bool:
        """Wait for the latest segment."""
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
        self, request: web.Request, token: str, sequence: str = "", part_num: str = ""
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

        return await self.handle(request, stream, sequence, part_num)

    async def handle(
        self, request: web.Request, stream: Stream, sequence: str, part_num: str
    ) -> web.StreamResponse:
        """Handle the stream request."""
        raise NotImplementedError()
