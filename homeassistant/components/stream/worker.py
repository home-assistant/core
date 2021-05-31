"""Provides the worker thread needed for processing streams."""
from __future__ import annotations

from collections import deque
from collections.abc import Iterator, Mapping, ValuesView
from fractions import Fraction
from io import BytesIO
import logging
from threading import Event
from typing import Callable, cast

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


class SegmentBuffer:
    """Buffer for writing a sequence of packets to the output as a segment."""

    def __init__(
        self, outputs_callback: Callable[[], Mapping[str, StreamOutput]]
    ) -> None:
        """Initialize SegmentBuffer."""
        self._stream_id: int = 0
        self._outputs_callback: Callable[
            [], Mapping[str, StreamOutput]
        ] = outputs_callback
        # Each element is a StreamOutput
        self._outputs: ValuesView[StreamOutput] | list[StreamOutput] = []
        # sequence gets incremented before the first segment so the first segment
        # has a sequence number of 0.
        self._sequence = -1
        self._segment_start_pts: int = cast(int, None)
        self._memory_file: BytesIO = cast(BytesIO, None)
        self._av_output: av.container.OutputContainer = None
        self._input_video_stream: av.video.VideoStream = None
        self._input_audio_stream = None  # av.audio.AudioStream | None
        self._output_video_stream: av.video.VideoStream = None
        self._output_audio_stream = None  # av.audio.AudioStream | None
        self._segment: Segment = cast(Segment, None)
        self._part_start_dts: int = cast(int, None)
        self._last_packet_dts: int = cast(int, None)
        self._part_is_independent = False
        self._last_packet_independent = False

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
                "avoid_negative_ts": "disabled",
                "fragment_index": str(sequence + 1),
                "video_track_timescale": str(int(1 / input_vstream.time_base)),
                "frag_duration": str(int(TARGET_PART_DURATION * 1e6)),
            },
        )

    def set_streams(
        self,
        video_stream: av.video.VideoStream,
        audio_stream,
        # no type hint for audio_stream until https://github.com/PyAV-Org/PyAV/pull/775 is merged
    ) -> None:
        """Initialize output buffer with streams from container."""
        self._input_video_stream = video_stream
        self._input_audio_stream = audio_stream

    def reset(self, video_pts: int) -> None:
        """Initialize a new stream segment."""
        # Keep track of the number of segments we've processed
        self._sequence += 1
        self._segment_start_pts = (
            self._part_start_dts
        ) = self._last_packet_dts = video_pts
        self._segment = Segment(sequence=self._sequence, stream_id=self._stream_id)
        self._memory_file = BytesIO()
        self._av_output = self.make_new_av(
            memory_file=self._memory_file,
            sequence=self._sequence,
            input_vstream=self._input_video_stream,
        )
        self._output_video_stream = self._av_output.add_stream(
            template=self._input_video_stream
        )
        # Check if audio is requested
        self._output_audio_stream = None
        if self._input_audio_stream and self._input_audio_stream.name in AUDIO_CODECS:
            self._output_audio_stream = self._av_output.add_stream(
                template=self._input_audio_stream
            )

    def mux_packet(self, packet: av.Packet) -> None:
        """Mux a packet to the appropriate output stream."""

        # Check for end of segment
        if packet.stream == self._input_video_stream:

            self.check_flush_part(packet)

            if (
                packet.is_keyframe
                and (
                    segment_duration := (packet.pts - self._segment_start_pts)
                    * packet.time_base
                )
                >= MIN_SEGMENT_DURATION
            ):
                # Flush segment (also flushes the stub part segment)
                self.flush(segment_duration, packet)

                # Reinitialize
                self.reset(packet.pts)

            self._last_packet_dts = packet.dts
            self._part_is_independent |= self._last_packet_independent
            self._last_packet_independent = packet.is_keyframe

        # Mux the packet
        if packet.stream == self._input_video_stream:
            packet.stream = self._output_video_stream
            self._av_output.mux(packet)
        elif packet.stream == self._input_audio_stream:
            packet.stream = self._output_audio_stream
            self._av_output.mux(packet)

    def check_flush_part(self, packet: av.Packet) -> None:
        """Check for and mark a part segment boundary and record its duration."""
        byte_position = self._memory_file.tell()
        if self._segment.last_write_pos == byte_position:
            return
        if self._segment.last_write_pos == 0:  # The beginning of the first moof
            self._segment.last_write_pos = byte_position
            self._segment.init = self._memory_file.getbuffer()[:byte_position].tobytes()
            # Fetch the latest StreamOutputs, which may have changed since the
            # worker started.
            self._outputs = self._outputs_callback().values()
            for stream_output in self._outputs:
                stream_output.put(self._segment)
        else:  # These are the ends of the part segments
            self._segment.parts.append(
                Part(
                    # The end of a part segment will actually have occurred before the last video packet
                    duration=float(
                        (self._last_packet_dts - self._part_start_dts)
                        * packet.time_base
                    ),
                    independent=self._part_is_independent,
                    data=self._memory_file.getbuffer()[
                        self._segment.last_write_pos : byte_position
                    ].tobytes(),
                )
            )
            self._segment.last_write_pos = byte_position
            self._part_start_dts = self._last_packet_dts
            self._part_is_independent = False

    def flush(self, duration: Fraction, packet: av.Packet) -> None:
        """Create a segment from the buffered packets and write to output."""
        self._av_output.close()
        self._segment.duration = float(duration)
        # Also flush the part segment (need to close the output above before this)
        end_loc = self._memory_file.tell()
        self._segment.parts.append(
            Part(
                duration=float((packet.pts - self._part_start_dts) * packet.time_base),
                independent=self._part_is_independent | self._last_packet_independent,
                data=self._memory_file.getbuffer()[
                    self._segment.last_write_pos :
                ].tobytes(),
            )
        )
        self._segment.last_write_pos = end_loc
        self._memory_file.close()  # We don't need the BytesIO object anymore

    def discontinuity(self) -> None:
        """Mark the stream as having been restarted."""
        # Preserving sequence and stream_id here keep the HLS playlist logic
        # simple to check for discontinuity at output time, and to determine
        # the discontinuity sequence number.
        self._stream_id += 1

    def close(self) -> None:
        """Close stream buffer."""
        self._av_output.close()
        self._memory_file.close()


def stream_worker(  # noqa: C901
    source: str, options: dict, segment_buffer: SegmentBuffer, quit_event: Event
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
    # These formats need aac_adtstoasc bitstream filter, but auto_bsf not
    # compatible with empty_moov and manual bitstream filters not in PyAV
    if container.format.name in {"hls", "mpegts"}:
        audio_stream = None
    # Some audio streams do not have a profile and throw errors when remuxing
    if audio_stream and audio_stream.profile is None:
        audio_stream = None

    # Iterator for demuxing
    container_packets: Iterator[av.Packet]
    # The decoder timestamps of the latest packet in each stream we processed
    last_dts = {video_stream: float("-inf"), audio_stream: float("-inf")}
    # Keep track of consecutive packets without a dts to detect end of stream.
    missing_dts = 0
    # The video pts at the beginning of the segment
    segment_start_pts: int | None = None
    # Because of problems 1 and 2 below, we need to store the first few packets and replay them
    initial_packets: deque[av.Packet] = deque()

    # Have to work around two problems with RTSP feeds in ffmpeg
    # 1 - first frame has bad pts/dts https://trac.ffmpeg.org/ticket/5018
    # 2 - seeking can be problematic https://trac.ffmpeg.org/ticket/7815

    def peek_first_pts() -> bool:
        """Initialize by peeking into the first few packets of the stream.

        Deal with problem #1 above (bad first packet pts/dts) by recalculating using pts/dts from second packet.
        Also load the first video keyframe pts into segment_start_pts and check if the audio stream really exists.
        """
        nonlocal segment_start_pts, audio_stream, container_packets
        missing_dts = 0
        found_audio = False
        try:
            container_packets = container.demux((video_stream, audio_stream))
            first_packet = None
            # Get to first video keyframe
            while first_packet is None:
                packet = next(container_packets)
                if (
                    packet.dts is None
                ):  # Allow MAX_MISSING_DTS packets with no dts, raise error on the next one
                    if missing_dts >= MAX_MISSING_DTS:
                        raise StopIteration(
                            f"Invalid data - got {MAX_MISSING_DTS+1} packets with missing DTS while initializing"
                        )
                    missing_dts += 1
                    continue
                if packet.stream == audio_stream:
                    found_audio = True
                elif packet.is_keyframe:  # video_keyframe
                    first_packet = packet
                    initial_packets.append(packet)
            # Get first_pts from subsequent frame to first keyframe
            while segment_start_pts is None or (
                audio_stream
                and not found_audio
                and len(initial_packets) < PACKETS_TO_WAIT_FOR_AUDIO
            ):
                packet = next(container_packets)
                if (
                    packet.dts is None
                ):  # Allow MAX_MISSING_DTS packet with no dts, raise error on the next one
                    if missing_dts >= MAX_MISSING_DTS:
                        raise StopIteration(
                            f"Invalid data - got {MAX_MISSING_DTS+1} packets with missing DTS while initializing"
                        )
                    missing_dts += 1
                    continue
                if packet.stream == audio_stream:
                    # detect ADTS AAC and disable audio
                    if audio_stream.codec.name == "aac" and packet.size > 2:
                        with memoryview(packet) as packet_view:
                            if packet_view[0] == 0xFF and packet_view[1] & 0xF0 == 0xF0:
                                _LOGGER.warning(
                                    "ADTS AAC detected - disabling audio stream"
                                )
                                container_packets = container.demux(video_stream)
                                audio_stream = None
                                continue
                    found_audio = True
                elif (
                    segment_start_pts is None
                ):  # This is the second video frame to calculate first_pts from
                    segment_start_pts = packet.dts - packet.duration
                    first_packet.pts = segment_start_pts
                    first_packet.dts = segment_start_pts
                initial_packets.append(packet)
            if audio_stream and not found_audio:
                _LOGGER.warning(
                    "Audio stream not found"
                )  # Some streams declare an audio stream and never send any packets
                audio_stream = None

        except (av.AVError, StopIteration) as ex:
            _LOGGER.error(
                "Error demuxing stream while finding first packet: %s", str(ex)
            )
            return False
        return True

    if not peek_first_pts():
        container.close()
        return

    segment_buffer.set_streams(video_stream, audio_stream)
    assert isinstance(segment_start_pts, int)
    segment_buffer.reset(segment_start_pts)

    while not quit_event.is_set():
        try:
            if len(initial_packets) > 0:
                packet = initial_packets.popleft()
            else:
                packet = next(container_packets)
            if packet.dts is None:
                # Allow MAX_MISSING_DTS consecutive packets without dts. Terminate the stream on the next one.
                if missing_dts >= MAX_MISSING_DTS:
                    raise StopIteration(
                        f"No dts in {MAX_MISSING_DTS+1} consecutive packets"
                    )
                missing_dts += 1
                continue
            missing_dts = 0
        except (av.AVError, StopIteration) as ex:
            _LOGGER.error("Error demuxing stream: %s", str(ex))
            break

        # Discard packet if dts is not monotonic
        if packet.dts <= last_dts[packet.stream]:
            if (
                packet.time_base * (last_dts[packet.stream] - packet.dts)
                > MAX_TIMESTAMP_GAP
            ):
                _LOGGER.warning(
                    "Timestamp overflow detected: last dts %s, dts = %s, resetting stream",
                    last_dts[packet.stream],
                    packet.dts,
                )
                break
            continue

        # Update last_dts processed
        last_dts[packet.stream] = packet.dts

        # Mux packets, and possibly write a segment to the output stream.
        # This mutates packet timestamps and stream
        segment_buffer.mux_packet(packet)

    # Close stream
    segment_buffer.close()
    container.close()
