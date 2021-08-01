"""Provides the worker thread needed for processing streams."""
from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Generator, Iterator, Mapping
from io import BytesIO
import itertools
import logging
from threading import Event
from typing import Any, Callable, cast

import av

from . import redact_credentials
from .const import (
    AUDIO_CODECS,
    MAX_MISSING_DTS,
    MAX_TIMESTAMP_GAP,
    MIN_SEGMENT_DURATION,
    PACKETS_TO_WAIT_FOR_AUDIO,
    SEGMENT_CONTAINER_FORMAT,
    SOURCE_TIMEOUT,
    TARGET_PART_DURATION,
)
from .core import Part, Segment, StreamOutput

_LOGGER = logging.getLogger(__name__)


class StreamState:
    """Responsible for tracking output and playback state for a stream.

    Holds state used for playback to interpret a decoded stream. A source stream
    may be reset (e.g. reconnecting to an rtsp stream) and this object tracks
    the state to inform the player.
    """

    def __init__(
        self,
        outputs_callback: Callable[[], Mapping[str, StreamOutput]],
    ) -> None:
        """Initialize StreamState."""
        self._stream_id: int = 0
        self._outputs_callback: Callable[
            [], Mapping[str, StreamOutput]
        ] = outputs_callback
        # sequence gets incremented before the first segment so the first segment
        # has a sequence number of 0.
        self._sequence = -1

    @property
    def sequence(self) -> int:
        """Return the current sequence for the latest segment."""
        return self._sequence

    def next_sequence(self) -> int:
        """Increment the sequence number."""
        self._sequence += 1
        return self._sequence

    @property
    def stream_id(self) -> int:
        """Return the readonly stream_id attribute."""
        return self._stream_id

    def discontinuity(self) -> None:
        """Mark the stream as having been restarted."""
        # Preserving sequence and stream_id here keep the HLS playlist logic
        # simple to check for discontinuity at output time, and to determine
        # the discontinuity sequence number.
        self._stream_id += 1

    def outputs(self) -> list[StreamOutput]:
        """Return the active stream outputs."""
        return list(self._outputs_callback().values())


class StreamMuxer:
    """StreamMuxer re-packages video/audio packets for output."""

    def __init__(
        self,
        video_stream: av.video.VideoStream,
        audio_stream: av.audio.stream.AudioStream | None,
    ) -> None:
        """Initialize StreamMuxer."""
        self._input_video_stream = video_stream
        self._input_audio_stream = audio_stream
        self._memory_file: BytesIO = cast(BytesIO, None)
        self._memory_file_pos = 0
        self._av_output: av.container.OutputContainer = None
        self._output_video_stream: av.video.VideoStream = None
        self._output_audio_stream: av.audio.stream.AudioStream | None = None

    @staticmethod
    def make_new_av(
        memory_file: BytesIO, sequence: int, input_vstream: av.video.VideoStream
    ) -> av.container.OutputContainer:
        """Make a new av OutputContainer."""
        return av.open(
            memory_file,
            mode="w",
            format=SEGMENT_CONTAINER_FORMAT,
            container_options={
                # Removed skip_sidx - see https://github.com/home-assistant/core/pull/39970
                # "cmaf" flag replaces several of the movflags used, but too recent to use for now
                "movflags": "empty_moov+default_base_moof+frag_discont+negative_cts_offsets+skip_trailer",
                # Sometimes the first segment begins with negative timestamps, and this setting just
                # adjusts the timestamps in the output from that segment to start from 0. Helps from
                # having to make some adjustments in test_durations
                "avoid_negative_ts": "make_non_negative",
                "fragment_index": str(sequence + 1),
                "video_track_timescale": str(int(1 / input_vstream.time_base)),
                # Create a fragments every TARGET_PART_DURATION. The data from each fragment is stored in
                # a "Part" that can be combined with the data from all the other "Part"s, plus an init
                # section, to reconstitute the data in a "Segment".
                "frag_duration": str(int(TARGET_PART_DURATION * 1e6)),
            },
        )

    def reset(self, sequence: int) -> None:
        """Initialize a new stream segment."""
        self._memory_file = BytesIO()
        self._memory_file_pos = 0
        self._av_output = self.make_new_av(
            memory_file=self._memory_file,
            sequence=sequence,
            input_vstream=self._input_video_stream,
        )
        self._output_video_stream = self._av_output.add_stream(
            template=self._input_video_stream
        )
        if self._input_audio_stream:
            self._output_audio_stream = self._av_output.add_stream(
                template=self._input_audio_stream
            )

    def mux_packet(self, packet: av.Packet) -> None:
        """Mux a packet to the appropriate output stream."""
        if packet.stream == self._input_video_stream:
            packet.stream = self._output_video_stream
            self._av_output.mux(packet)
        elif packet.stream == self._input_audio_stream:
            packet.stream = self._output_audio_stream
            self._av_output.mux(packet)

    def close(self) -> bytes | None:
        """Close stream buffer and return pending output data."""
        self._av_output.close()
        data = self.read()
        self._memory_file.close()
        return data

    def read(self) -> bytes | None:
        """Read output bytes of muxed packets.

        Returns: A tuple of bytes read and whether or not the bytes
            contain a key frame.
        """
        if self._memory_file_pos == self._memory_file.tell():
            return None
        self._memory_file.seek(self._memory_file_pos)
        data = self._memory_file.read()
        self._memory_file_pos = self._memory_file.tell()
        return data


class PeekIterator(Iterator):
    """An Iterator that may allow multiple passes.

    This may be consumed like a normal Iterator, however also supports a
    peek() method that buffers consumed items from the iterator.
    """

    def __init__(self, iterator: Iterator[av.Packet]) -> None:
        """Initialize PeekIterator."""
        self._iterator = iterator
        self._buffer: deque[av.Packet] = deque()
        # A pointer to either _iterator or _buffer
        self._next = self._iterator.__next__

    def __iter__(self) -> Iterator:
        """Return an iterator."""
        return self

    def __next__(self) -> av.Packet:
        """Return and consume the next item available."""
        return self._next()

    def replace_underlying_iterator(self, new_iterator: Iterator) -> None:
        """Replace the underlying iterator while preserving the buffer."""
        self._iterator = new_iterator
        if not self._buffer:
            self._next = self._iterator.__next__

    def _pop_buffer(self) -> av.Packet:
        """Consume items from the buffer until exhausted."""
        if self._buffer:
            return self._buffer.popleft()
        # The buffer is empty, so change to consume from the iterator
        self._next = self._iterator.__next__
        return self._next()

    def peek(self) -> Generator[av.Packet, None, None]:
        """Return items without consuming from the iterator."""
        # Items consumed are added to a buffer for future calls to __next__
        # or peek. First iterate over the buffer from previous calls to peek.
        self._next = self._pop_buffer
        for packet in self._buffer:
            yield packet
        for packet in self._iterator:
            self._buffer.append(packet)
            yield packet


class TimestampValidator:
    """Validate ordering of timestamps for packets in a stream."""

    def __init__(self) -> None:
        """Initialize the TimestampValidator."""
        # Decompression timestamp of last packet in each stream
        self._last_dts: dict[av.stream.Stream, int | float] = defaultdict(
            lambda: float("-inf")
        )
        # Number of consecutive missing decompression timestamps
        self._missing_dts = 0

    def is_valid(self, packet: av.Packet) -> bool:
        """Validate the packet timestamp based on ordering within the stream."""
        # Discard packets missing DTS. Terminate if too many are missing.
        if packet.dts is None:
            if self._missing_dts >= MAX_MISSING_DTS:
                raise StopIteration(
                    f"No dts in {MAX_MISSING_DTS+1} consecutive packets"
                )
            self._missing_dts += 1
            return False
        self._missing_dts = 0
        # Discard when dts is not monotonic. Terminate if gap is too wide.
        prev_dts = self._last_dts[packet.stream]
        if packet.dts <= prev_dts:
            gap = packet.time_base * (prev_dts - packet.dts)
            if gap > MAX_TIMESTAMP_GAP:
                raise StopIteration(
                    f"Timestamp overflow detected: last dts = {prev_dts}, dts = {packet.dts}"
                )
            return False
        self._last_dts[packet.stream] = packet.dts
        return True


def is_keyframe(packet: av.Packet) -> Any:
    """Return true if the packet is a keyframe."""
    return packet.is_keyframe


def unsupported_audio(packets: Iterator[av.Packet], audio_stream: Any) -> bool:
    """Detect ADTS AAC, which is not supported by pyav."""
    if not audio_stream:
        return False
    for count, packet in enumerate(packets):
        if count >= PACKETS_TO_WAIT_FOR_AUDIO:
            # Some streams declare an audio stream and never send any packets
            _LOGGER.warning("Audio stream not found")
            break
        if packet.stream == audio_stream:
            # detect ADTS AAC and disable audio
            if audio_stream.codec.name == "aac" and packet.size > 2:
                with memoryview(packet) as packet_view:
                    if packet_view[0] == 0xFF and packet_view[1] & 0xF0 == 0xF0:
                        _LOGGER.warning("ADTS AAC detected - disabling audio stream")
                        return True
            break
    return False


def packet_interval(packet: av.Packet, start_dts: int) -> float:
    """Return time interval from start_dts to packet.dts."""
    return float((packet.dts - start_dts) * packet.time_base)


def stream_worker(
    source: str,
    options: dict[str, str],
    stream_state: StreamState,
    quit_event: Event,
) -> None:
    """Handle consuming streams."""

    try:
        container = av.open(source, options=options, timeout=SOURCE_TIMEOUT)
    except av.AVError:
        _LOGGER.error("Error opening stream %s", redact_credentials(str(source)))
        return
    try:
        video_stream = container.streams.video[0]
    except (KeyError, IndexError):
        _LOGGER.error("Stream has no video")
        container.close()
        return
    try:
        audio_stream = container.streams.audio[0]
    except (KeyError, IndexError):
        audio_stream = None
    if audio_stream and audio_stream.name not in AUDIO_CODECS:
        audio_stream = None
    # These formats need aac_adtstoasc bitstream filter, but auto_bsf not
    # compatible with empty_moov and manual bitstream filters not in PyAV
    if container.format.name in {"hls", "mpegts"}:
        audio_stream = None
    # Some audio streams do not have a profile and throw errors when remuxing
    if audio_stream and audio_stream.profile is None:
        audio_stream = None

    dts_validator = TimestampValidator()
    container_packets = PeekIterator(
        filter(dts_validator.is_valid, container.demux((video_stream, audio_stream)))
    )

    def is_video(packet: av.Packet) -> Any:
        """Return true if the packet is for the video stream."""
        return packet.stream == video_stream

    # Have to work around two problems with RTSP feeds in ffmpeg
    # 1 - first frame has bad pts/dts https://trac.ffmpeg.org/ticket/5018
    # 2 - seeking can be problematic https://trac.ffmpeg.org/ticket/7815
    #
    # Use a peeking iterator to peek into the start of the stream, ensuring
    # everything looks good, then go back to the start when muxing below.
    try:
        if audio_stream and unsupported_audio(container_packets.peek(), audio_stream):
            audio_stream = None
            container_packets.replace_underlying_iterator(
                filter(dts_validator.is_valid, container.demux(video_stream))
            )

        # Advance to the first keyframe for muxing, then rewind so the muxing
        # loop below can consume.
        first_keyframe = next(
            filter(lambda pkt: is_keyframe(pkt) and is_video(pkt), container_packets)
        )
        # Deal with problem #1 above (bad first packet pts/dts) by recalculating
        # using pts/dts from second packet. Use the peek iterator to advance
        # without consuming from container_packets. Skip over the first keyframe
        # then use the duration from the second video packet to adjust dts.
        next_video_packet = next(filter(is_video, container_packets.peek()))
        # Since the is_valid filter has already been applied before the following
        # adjustment, it does not filter out the case where the duration below is
        # 0 and both the first_keyframe and next_video_packet end up with the same
        # dts. Use "or 1" to deal with this.
        start_dts = next_video_packet.dts - (next_video_packet.duration or 1)
        first_keyframe.dts = first_keyframe.pts = start_dts
    except (av.AVError, StopIteration) as ex:
        _LOGGER.error("Error demuxing stream while finding first packet: %s", str(ex))
        container.close()
        return

    muxer = StreamMuxer(video_stream, audio_stream)
    muxer.reset(stream_state.next_sequence())

    segment: Segment | None = None
    part_has_keyframe = False

    # Mux the first keyframe, then proceed through the rest of the packets
    packets = itertools.chain([first_keyframe], container_packets)
    while not quit_event.is_set():
        try:
            packet = next(packets)
        except (av.AVError, StopIteration) as ex:
            _LOGGER.error("Error demuxing stream: %s", str(ex))
            break

        if not is_video(packet):
            muxer.mux_packet(packet)
            continue

        # Check for end of segment
        if segment and packet.is_keyframe:
            segment_duration = packet_interval(packet, segment.dts)
            if segment_duration >= MIN_SEGMENT_DURATION:
                # Flush segment (also flushes the stub part segment)
                data = muxer.close()
                assert data
                segment.parts.append(
                    Part(
                        duration=packet_interval(packet, segment.current_dts),
                        has_keyframe=part_has_keyframe,
                        data=data,
                        dts=packet.dts,
                    )
                )
                part_has_keyframe = False
                segment.duration = segment_duration
                # Reinitialize
                muxer.reset(stream_state.next_sequence())
                segment = None

        # Mux the packet
        muxer.mux_packet(packet)
        data = muxer.read()
        if data:
            if segment is None:
                # We have our first non-zero byte position. This means the init has just
                # been written. Put the segment in the queue of each output.
                segment = Segment(
                    sequence=stream_state.sequence,
                    dts=packet.dts,
                    stream_id=stream_state.stream_id,
                    init=data,
                )
                # Fetch the latest StreamOutputs, which may have changed since the
                # worker started.
                for stream_output in stream_state.outputs():
                    stream_output.put(segment)
            else:  # These are the ends of the part segments
                segment.parts.append(
                    Part(
                        duration=packet_interval(packet, segment.current_dts),
                        has_keyframe=part_has_keyframe,
                        data=data,
                        dts=packet.dts,
                    )
                )
                part_has_keyframe = False
        part_has_keyframe |= packet.is_keyframe

    # Close stream
    muxer.close()
    container.close()
