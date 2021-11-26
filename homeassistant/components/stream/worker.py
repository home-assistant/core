"""Provides the worker thread needed for processing streams."""
from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Generator, Iterator, Mapping
import datetime
from io import BytesIO
import logging
from threading import Event
from typing import Any, cast

import av

from homeassistant.core import HomeAssistant

from . import redact_credentials
from .const import (
    ATTR_SETTINGS,
    AUDIO_CODECS,
    DOMAIN,
    HLS_PROVIDER,
    MAX_MISSING_DTS,
    MAX_TIMESTAMP_GAP,
    PACKETS_TO_WAIT_FOR_AUDIO,
    SEGMENT_CONTAINER_FORMAT,
    SOURCE_TIMEOUT,
)
from .core import Part, Segment, StreamOutput, StreamSettings
from .hls import HlsStreamOutput

_LOGGER = logging.getLogger(__name__)


class SegmentBuffer:
    """Buffer for writing a sequence of packets to the output as a segment."""

    def __init__(
        self,
        hass: HomeAssistant,
        outputs_callback: Callable[[], Mapping[str, StreamOutput]],
    ) -> None:
        """Initialize SegmentBuffer."""
        self._stream_id: int = 0
        self._hass = hass
        self._outputs_callback: Callable[
            [], Mapping[str, StreamOutput]
        ] = outputs_callback
        # sequence gets incremented before the first segment so the first segment
        # has a sequence number of 0.
        self._sequence = -1
        self._segment_start_dts: int = cast(int, None)
        self._memory_file: BytesIO = cast(BytesIO, None)
        self._av_output: av.container.OutputContainer = None
        self._input_video_stream: av.video.VideoStream = None
        self._input_audio_stream: av.audio.stream.AudioStream | None = None
        self._output_video_stream: av.video.VideoStream = None
        self._output_audio_stream: av.audio.stream.AudioStream | None = None
        self._segment: Segment | None = None
        # the following 3 member variables are used for Part formation
        self._memory_file_pos: int = cast(int, None)
        self._part_start_dts: int = cast(int, None)
        self._part_has_keyframe = False
        self._stream_settings: StreamSettings = hass.data[DOMAIN][ATTR_SETTINGS]
        self._start_time = datetime.datetime.utcnow()

    def make_new_av(
        self,
        memory_file: BytesIO,
        sequence: int,
        input_vstream: av.video.VideoStream,
        input_astream: av.audio.stream.AudioStream,
    ) -> tuple[
        av.container.OutputContainer,
        av.video.VideoStream,
        av.audio.stream.AudioStream | None,
    ]:
        """Make a new av OutputContainer and add output streams."""
        add_audio = input_astream and input_astream.name in AUDIO_CODECS
        container = av.open(
            memory_file,
            mode="w",
            format=SEGMENT_CONTAINER_FORMAT,
            container_options={
                **{
                    # Removed skip_sidx - see https://github.com/home-assistant/core/pull/39970
                    # "cmaf" flag replaces several of the movflags used, but too recent to use for now
                    "movflags": "frag_custom+empty_moov+default_base_moof+frag_discont+negative_cts_offsets+skip_trailer",
                    # Sometimes the first segment begins with negative timestamps, and this setting just
                    # adjusts the timestamps in the output from that segment to start from 0. Helps from
                    # having to make some adjustments in test_durations
                    "avoid_negative_ts": "make_non_negative",
                    "fragment_index": str(sequence + 1),
                    "video_track_timescale": str(int(1 / input_vstream.time_base)),
                },
                # Only do extra fragmenting if we are using ll_hls
                # Let ffmpeg do the work using frag_duration
                # Fragment durations may exceed the 15% allowed variance but it seems ok
                **(
                    {
                        "movflags": "empty_moov+default_base_moof+frag_discont+negative_cts_offsets+skip_trailer",
                        # Create a fragment every TARGET_PART_DURATION. The data from each fragment is stored in
                        # a "Part" that can be combined with the data from all the other "Part"s, plus an init
                        # section, to reconstitute the data in a "Segment".
                        # The LL-HLS spec allows for a fragment's duration to be within the range [0.85x,1.0x]
                        # of the part target duration. We use the frag_duration option to tell ffmpeg to try to
                        # cut the fragments when they reach frag_duration. However, the resulting fragments can
                        # have variability in their durations and can end up being too short or too long. With a
                        # video track with no audio, the discrete nature of frames means that the frame at the
                        # end of a fragment will sometimes extend slightly beyond the desired frag_duration.
                        # If there are two tracks, as in the case of a video feed with audio, there is an added
                        # wrinkle as the fragment cut seems to be done on the first track that crosses the desired
                        # threshold, and cutting on the audio track may also result in a shorter video fragment
                        # than desired.
                        # Given this, our approach is to give ffmpeg a frag_duration somewhere in the middle
                        # of the range, hoping that the parts stay pretty well bounded, and we adjust the part
                        # durations a bit in the hls metadata so that everything "looks" ok.
                        "frag_duration": str(
                            self._stream_settings.part_target_duration * 9e5
                        ),
                    }
                    if self._stream_settings.ll_hls
                    else {}
                ),
            },
        )
        output_vstream = container.add_stream(template=input_vstream)
        # Check if audio is requested
        output_astream = None
        if add_audio:
            output_astream = container.add_stream(template=input_astream)
        return container, output_vstream, output_astream

    def set_streams(
        self,
        video_stream: av.video.VideoStream,
        audio_stream: Any,
        # no type hint for audio_stream until https://github.com/PyAV-Org/PyAV/pull/775 is merged
    ) -> None:
        """Initialize output buffer with streams from container."""
        self._input_video_stream = video_stream
        self._input_audio_stream = audio_stream

    def reset(self, video_dts: int) -> None:
        """Initialize a new stream segment."""
        # Keep track of the number of segments we've processed
        self._sequence += 1
        self._part_start_dts = self._segment_start_dts = video_dts
        self._segment = None
        self._memory_file = BytesIO()
        self._memory_file_pos = 0
        (
            self._av_output,
            self._output_video_stream,
            self._output_audio_stream,
        ) = self.make_new_av(
            memory_file=self._memory_file,
            sequence=self._sequence,
            input_vstream=self._input_video_stream,
            input_astream=self._input_audio_stream,
        )
        if self._output_video_stream.name == "hevc":
            self._output_video_stream.codec_tag = "hvc1"

    def mux_packet(self, packet: av.Packet) -> None:
        """Mux a packet to the appropriate output stream."""

        # Check for end of segment
        if packet.stream == self._input_video_stream:
            if (
                packet.is_keyframe
                and (packet.dts - self._segment_start_dts) * packet.time_base
                >= self._stream_settings.min_segment_duration
            ):
                # Flush segment (also flushes the stub part segment)
                self.flush(packet, last_part=True)

            # Mux the packet
            packet.stream = self._output_video_stream
            self._av_output.mux(packet)
            self.check_flush_part(packet)
            self._part_has_keyframe |= packet.is_keyframe

        elif packet.stream == self._input_audio_stream:
            packet.stream = self._output_audio_stream
            self._av_output.mux(packet)

    def check_flush_part(self, packet: av.Packet) -> None:
        """Check for and mark a part segment boundary and record its duration."""
        if self._memory_file_pos == self._memory_file.tell():
            return
        if self._segment is None:
            # We have our first non-zero byte position. This means the init has just
            # been written. Create a Segment and put it to the queue of each output.
            self._segment = Segment(
                sequence=self._sequence,
                stream_id=self._stream_id,
                init=self._memory_file.getvalue(),
                # Fetch the latest StreamOutputs, which may have changed since the
                # worker started.
                stream_outputs=self._outputs_callback().values(),
                start_time=self._start_time,
            )
            self._memory_file_pos = self._memory_file.tell()
        else:  # These are the ends of the part segments
            self.flush(packet, last_part=False)

    def flush(self, packet: av.Packet, last_part: bool) -> None:
        """Output a part from the most recent bytes in the memory_file.

        If last_part is True, also close the segment, give it a duration,
        and clean up the av_output and memory_file.
        There are two different ways to enter this function, and when
        last_part is True, packet has not yet been muxed, while when
        last_part is False, the packet has already been muxed. However,
        in both cases, packet is the next packet and is not included in
        the Part.
        This function writes the duration metadata for the Part and
        for the Segment. However, as the fragmentation done by ffmpeg
        may result in fragment durations which fall outside the
        [0.85x,1.0x] tolerance band allowed by LL-HLS, we need to fudge
        some durations a bit by reporting them as being within that
        range.
        Note that repeated adjustments may cause drift between the part
        durations in the metadata and those in the media and result in
        playback issues in some clients.
        """
        # Part durations should not exceed the part target duration
        adjusted_dts = min(
            packet.dts,
            self._part_start_dts
            + self._stream_settings.part_target_duration / packet.time_base,
        )
        if last_part:
            # Closing the av_output will write the remaining buffered data to the
            # memory_file as a new moof/mdat.
            self._av_output.close()
        elif not self._part_has_keyframe:
            # Parts which are not the last part or an independent part should
            # not have durations below 0.85 of the part target duration.
            adjusted_dts = max(
                adjusted_dts,
                self._part_start_dts
                + 0.85 * self._stream_settings.part_target_duration / packet.time_base,
            )
        assert self._segment
        self._memory_file.seek(self._memory_file_pos)
        self._hass.loop.call_soon_threadsafe(
            self._segment.async_add_part,
            Part(
                duration=float(
                    (adjusted_dts - self._part_start_dts) * packet.time_base
                ),
                has_keyframe=self._part_has_keyframe,
                data=self._memory_file.read(),
            ),
            (
                segment_duration := float(
                    (adjusted_dts - self._segment_start_dts) * packet.time_base
                )
            )
            if last_part
            else 0,
        )
        if last_part:
            # If we've written the last part, we can close the memory_file.
            self._memory_file.close()  # We don't need the BytesIO object anymore
            self._start_time += datetime.timedelta(seconds=segment_duration)
            # Reinitialize
            self.reset(packet.dts)
        else:
            # For the last part, these will get set again elsewhere so we can skip
            # setting them here.
            self._memory_file_pos = self._memory_file.tell()
            self._part_start_dts = adjusted_dts
        self._part_has_keyframe = False

    def discontinuity(self) -> None:
        """Mark the stream as having been restarted."""
        # Preserving sequence and stream_id here keep the HLS playlist logic
        # simple to check for discontinuity at output time, and to determine
        # the discontinuity sequence number.
        self._stream_id += 1
        self._start_time = datetime.datetime.utcnow()
        # Call discontinuity to remove incomplete segment from the HLS output
        if hls_output := self._outputs_callback().get(HLS_PROVIDER):
            cast(HlsStreamOutput, hls_output).discontinuity()

    def close(self) -> None:
        """Close stream buffer."""
        self._av_output.close()
        self._memory_file.close()


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


def stream_worker(
    source: str,
    options: dict[str, str],
    segment_buffer: SegmentBuffer,
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

    segment_buffer.set_streams(video_stream, audio_stream)
    segment_buffer.reset(start_dts)

    # Mux the first keyframe, then proceed through the rest of the packets
    segment_buffer.mux_packet(first_keyframe)

    while not quit_event.is_set():
        try:
            packet = next(container_packets)
        except (av.AVError, StopIteration) as ex:
            _LOGGER.error("Error demuxing stream: %s", str(ex))
            break
        segment_buffer.mux_packet(packet)

    # Close stream
    segment_buffer.close()
    container.close()
