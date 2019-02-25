"""Provides core stream functionality."""
import asyncio
import io
from typing import List, Any

import attr


@attr.s
class StreamBuffer:
    """Represent a segment."""

    # pylint: disable=no-name-in-module
    from av import CodecContext
    from av.container import OutputContainer
    from av.video.stream import VideoStream
    from av.audio.stream import AudioStream

    segment = attr.ib(type=io.BytesIO)
    output = attr.ib(type=OutputContainer)
    vstream = attr.ib(type=VideoStream)
    astream = attr.ib(type=AudioStream, default=None)


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
        self.__cursor = None
        self.__event = asyncio.Event()
        self.__segments = []

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
        return [s.sequence for s in self.__segments]

    @property
    def target_duration(self) -> int:
        """Return the average duration of the segments in seconds."""
        durations = [s.duration for s in self.__segments]
        return round(sum(durations) // len(self.__segments)) or 1

    def get_segment(self, sequence: int = None) -> Any:
        """Retrieve a specific segment, or the whole list."""
        if not sequence:
            return self.__segments

        for segment in self.__segments:
            if segment.sequence == sequence:
                return segment
        return None

    async def recv(self) -> Segment:
        """Wait for and retrieve the latest segment."""
        if self.__cursor is None or self.__cursor <= max(self.segments):
            await self.__event.wait()
        segment = self.__segments[-1]
        self.__cursor = segment.sequence
        return segment

    async def put(self, segment: Segment) -> None:
        """Store output."""
        self.__segments.append(segment)
        if len(self.__segments) > self.num_segments:
            self.__segments = self.__segments[-self.num_segments:]
        self.__event.set()
        self.__event.clear()
