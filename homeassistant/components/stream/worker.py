"""Provides the worker thread needed for processing streams."""
from collections import deque
import io
import logging

import av

from . import redact_credentials
from .const import (
    AUDIO_CODECS,
    MAX_MISSING_DTS,
    MAX_TIMESTAMP_GAP,
    MIN_SEGMENT_DURATION,
    PACKETS_TO_WAIT_FOR_AUDIO,
    SEGMENT_CONTAINER_FORMAT,
    STREAM_TIMEOUT,
)
from .core import Segment, StreamBuffer

_LOGGER = logging.getLogger(__name__)


def create_stream_buffer(video_stream, audio_stream, sequence):
    """Create a new StreamBuffer."""

    segment = io.BytesIO()
    container_options = {
        # Removed skip_sidx - see https://github.com/home-assistant/core/pull/39970
        "movflags": "frag_custom+empty_moov+default_base_moof+frag_discont+negative_cts_offsets",
        "avoid_negative_ts": "disabled",
        "fragment_index": str(sequence),
    }
    output = av.open(
        segment,
        mode="w",
        format=SEGMENT_CONTAINER_FORMAT,
        container_options={
            "video_track_timescale": str(int(1 / video_stream.time_base)),
            **container_options,
        },
    )
    vstream = output.add_stream(template=video_stream)
    # Check if audio is requested
    astream = None
    if audio_stream and audio_stream.name in AUDIO_CODECS:
        astream = output.add_stream(template=audio_stream)
    return StreamBuffer(segment, output, vstream, astream)


class SegmentBuffer:
    """Buffer for writing a sequence of packets to the output as a segment."""

    def __init__(self, outputs_callback) -> None:
        """Initialize SegmentBuffer."""
        self._stream_id = 0
        self._video_stream = None
        self._audio_stream = None
        self._outputs_callback = outputs_callback
        # Each element is a StreamOutput
        self._outputs = []
        self._sequence = 0
        self._segment_start_pts = None
        self._stream_buffer = None

    def set_streams(self, video_stream, audio_stream):
        """Initialize output buffer with streams from container."""
        self._video_stream = video_stream
        self._audio_stream = audio_stream

    def reset(self, video_pts):
        """Initialize a new stream segment."""
        # Keep track of the number of segments we've processed
        self._sequence += 1
        self._segment_start_pts = video_pts

        # Fetch the latest StreamOutputs, which may have changed since the
        # worker started.
        self._outputs = self._outputs_callback().values()
        self._stream_buffer = create_stream_buffer(
            self._video_stream, self._audio_stream, self._sequence
        )

    def mux_packet(self, packet):
        """Mux a packet to the appropriate StreamBuffers."""

        # Check for end of segment
        if packet.stream == self._video_stream and packet.is_keyframe:
            duration = (packet.pts - self._segment_start_pts) * packet.time_base
            if duration >= MIN_SEGMENT_DURATION:
                # Save segment to outputs
                self.flush(duration)

                # Reinitialize
                self.reset(packet.pts)

        # Mux the packet
        if packet.stream == self._video_stream:
            packet.stream = self._stream_buffer.vstream
            self._stream_buffer.output.mux(packet)
        elif packet.stream == self._audio_stream:
            packet.stream = self._stream_buffer.astream
            self._stream_buffer.output.mux(packet)

    def flush(self, duration):
        """Create a segment from the buffered packets and write to output."""
        self._stream_buffer.output.close()
        segment = Segment(
            self._sequence, self._stream_buffer.segment, duration, self._stream_id
        )
        for stream_output in self._outputs:
            stream_output.put(segment)

    def discontinuity(self):
        """Mark the stream as having been restarted."""
        # Preserving sequence and stream_id here keep the HLS playlist logic
        # simple to check for discontinuity at output time, and to determine
        # the discontinuity sequence number.
        self._stream_id += 1

    def close(self):
        """Close stream buffer."""
        self._stream_buffer.output.close()


def stream_worker(source, options, segment_buffer, quit_event):  # noqa: C901
    """Handle consuming streams."""

    try:
        container = av.open(source, options=options, timeout=STREAM_TIMEOUT)
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
    container_packets = None
    # The decoder timestamps of the latest packet in each stream we processed
    last_dts = {video_stream: float("-inf"), audio_stream: float("-inf")}
    # Keep track of consecutive packets without a dts to detect end of stream.
    missing_dts = 0
    # The video pts at the beginning of the segment
    segment_start_pts = None
    # Because of problems 1 and 2 below, we need to store the first few packets and replay them
    initial_packets = deque()

    # Have to work around two problems with RTSP feeds in ffmpeg
    # 1 - first frame has bad pts/dts https://trac.ffmpeg.org/ticket/5018
    # 2 - seeking can be problematic https://trac.ffmpeg.org/ticket/7815

    def peek_first_pts():
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
