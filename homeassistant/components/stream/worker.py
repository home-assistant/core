"""Provides the worker thread needed for processing streams."""
from collections import deque
import io
import logging
import time

import av

from .const import (
    MAX_MISSING_DTS,
    MAX_TIMESTAMP_GAP,
    MIN_SEGMENT_DURATION,
    PACKETS_TO_WAIT_FOR_AUDIO,
    STREAM_RESTART_INCREMENT,
    STREAM_RESTART_RESET_TIME,
    STREAM_TIMEOUT,
)
from .core import Segment, StreamBuffer

_LOGGER = logging.getLogger(__name__)


def create_stream_buffer(stream_output, video_stream, audio_stream, sequence):
    """Create a new StreamBuffer."""

    segment = io.BytesIO()
    container_options = (
        stream_output.container_options(sequence)
        if stream_output.container_options
        else {}
    )
    output = av.open(
        segment,
        mode="w",
        format=stream_output.format,
        container_options={
            "video_track_timescale": str(int(1 / video_stream.time_base)),
            **container_options,
        },
    )
    vstream = output.add_stream(template=video_stream)
    # Check if audio is requested
    astream = None
    if audio_stream and audio_stream.name in stream_output.audio_codecs:
        astream = output.add_stream(template=audio_stream)
    return StreamBuffer(segment, output, vstream, astream)


def stream_worker(hass, stream, quit_event):
    """Handle consuming streams and restart keepalive streams."""

    wait_timeout = 0
    while not quit_event.wait(timeout=wait_timeout):
        start_time = time.time()
        try:
            _stream_worker_internal(hass, stream, quit_event)
        except av.error.FFmpegError:  # pylint: disable=c-extension-no-member
            _LOGGER.exception("Stream connection failed: %s", stream.source)
        if not stream.keepalive or quit_event.is_set():
            break
        # To avoid excessive restarts, wait before restarting
        # As the required recovery time may be different for different setups, start
        # with trying a short wait_timeout and increase it on each reconnection attempt.
        # Reset the wait_timeout after the worker has been up for several minutes
        if time.time() - start_time > STREAM_RESTART_RESET_TIME:
            wait_timeout = 0
        wait_timeout += STREAM_RESTART_INCREMENT
        _LOGGER.debug(
            "Restarting stream worker in %d seconds: %s",
            wait_timeout,
            stream.source,
        )


def _stream_worker_internal(hass, stream, quit_event):
    """Handle consuming streams."""

    try:
        container = av.open(
            stream.source, options=stream.options, timeout=STREAM_TIMEOUT
        )
    except av.AVError:
        _LOGGER.error("Error opening stream %s", stream.source)
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
    # Holds the buffers for each stream provider
    outputs = None
    # Keep track of the number of segments we've processed
    sequence = 0
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
            finalize_stream()
            return False
        return True

    def initialize_segment(video_pts):
        """Reset some variables and initialize outputs for each segment."""
        nonlocal outputs, sequence, segment_start_pts
        # Clear outputs and increment sequence
        outputs = {}
        sequence += 1
        segment_start_pts = video_pts
        for stream_output in stream.outputs.values():
            if video_stream.name not in stream_output.video_codecs:
                continue
            buffer = create_stream_buffer(
                stream_output, video_stream, audio_stream, sequence
            )
            outputs[stream_output.name] = (
                buffer,
                {video_stream: buffer.vstream, audio_stream: buffer.astream},
            )

    def mux_video_packet(packet):
        # mux packets to each buffer
        for buffer, output_streams in outputs.values():
            # Assign the packet to the new stream & mux
            packet.stream = output_streams[video_stream]
            buffer.output.mux(packet)

    def mux_audio_packet(packet):
        # almost the same as muxing video but add extra check
        for buffer, output_streams in outputs.values():
            # Assign the packet to the new stream & mux
            if output_streams.get(audio_stream):
                packet.stream = output_streams[audio_stream]
                buffer.output.mux(packet)

    def finalize_stream():
        if not stream.keepalive:
            # End of stream, clear listeners and stop thread
            for fmt in stream.outputs:
                stream.outputs[fmt].put(None)

    if not peek_first_pts():
        container.close()
        return

    initialize_segment(segment_start_pts)

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
            finalize_stream()
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
                finalize_stream()
                break
            continue

        # Check for end of segment
        if packet.stream == video_stream and packet.is_keyframe:
            segment_duration = (packet.pts - segment_start_pts) * packet.time_base
            if segment_duration >= MIN_SEGMENT_DURATION:
                # Save segment to outputs
                for fmt, (buffer, _) in outputs.items():
                    buffer.output.close()
                    if stream.outputs.get(fmt):
                        stream.outputs[fmt].put(
                            Segment(
                                sequence,
                                buffer.segment,
                                segment_duration,
                            ),
                        )

                # Reinitialize
                initialize_segment(packet.pts)

        # Update last_dts processed
        last_dts[packet.stream] = packet.dts
        # mux packets
        if packet.stream == video_stream:
            mux_video_packet(packet)  # mutates packet timestamps
        else:
            mux_audio_packet(packet)  # mutates packet timestamps

    # Close stream
    for buffer, _ in outputs.values():
        buffer.output.close()
    container.close()
