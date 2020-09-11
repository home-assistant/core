"""Provides the worker thread needed for processing streams."""
from collections import deque
import io
import logging
import time

import av

from .const import MIN_SEGMENT_DURATION, PACKETS_TO_WAIT_FOR_AUDIO
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
        container_options=container_options,
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
        # To avoid excessive restarts, don't restart faster than once every 40 seconds.
        wait_timeout = max(40 - (time.time() - start_time), 0)
        _LOGGER.debug(
            "Restarting stream worker in %d seconds: %s",
            wait_timeout,
            stream.source,
        )


def _stream_worker_internal(hass, stream, quit_event):
    """Handle consuming streams."""

    container = av.open(stream.source, options=stream.options)
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

    # The presentation timestamps of the first packet in each stream we receive
    # Use to adjust before muxing or outputting, but we don't adjust internally
    first_pts = {}
    # The decoder timestamps of the latest packet in each stream we processed
    last_dts = None
    # Keep track of consecutive packets without a dts to detect end of stream.
    last_packet_was_without_dts = False
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
        nonlocal first_pts, audio_stream

        def empty_stream_dict():
            return {
                video_stream: None,
                **({audio_stream: None} if audio_stream else {}),
            }

        try:
            first_packet = empty_stream_dict()
            first_pts = empty_stream_dict()
            # Get to first video keyframe
            while first_packet[video_stream] is None:
                packet = next(container.demux())
                if packet.stream == video_stream and packet.is_keyframe:
                    first_packet[video_stream] = packet
                    initial_packets.append(packet)
            # Get first_pts from subsequent frame to first keyframe
            while any(
                [pts is None for pts in {**first_packet, **first_pts}.values()]
            ) and (len(initial_packets) < PACKETS_TO_WAIT_FOR_AUDIO):
                packet = next(container.demux((video_stream, audio_stream)))
                if (
                    first_packet[packet.stream] is None
                ):  # actually video already found above so only for audio
                    if packet.is_keyframe:
                        first_packet[packet.stream] = packet
                    else:  # Discard leading non-keyframes
                        continue
                else:  # This is the second frame to calculate first_pts from
                    if first_pts[packet.stream] is None:
                        first_pts[packet.stream] = packet.dts - packet.duration
                        first_packet[packet.stream].pts = first_pts[packet.stream]
                        first_packet[packet.stream].dts = first_pts[packet.stream]
                initial_packets.append(packet)
            if audio_stream and first_packet[audio_stream] is None:
                _LOGGER.warning(
                    "Audio stream not found"
                )  # Some streams declare an audio stream and never send any packets
                del first_pts[audio_stream]
                audio_stream = None

        except (av.AVError, StopIteration) as ex:
            if not stream.keepalive:
                # End of stream, clear listeners and stop thread
                for fmt, _ in outputs.items():
                    hass.loop.call_soon_threadsafe(stream.outputs[fmt].put, None)
            _LOGGER.error(
                "Error demuxing stream while finding first packet: %s", str(ex)
            )
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
        # adjust pts and dts before muxing
        packet.pts -= first_pts[video_stream]
        packet.dts -= first_pts[video_stream]
        # mux packets to each buffer
        for buffer, output_streams in outputs.values():
            # Assign the packet to the new stream & mux
            packet.stream = output_streams[video_stream]
            buffer.output.mux(packet)

    def mux_audio_packet(packet):
        # almost the same as muxing video but add extra check
        # adjust pts and dts before muxing
        packet.pts -= first_pts[audio_stream]
        packet.dts -= first_pts[audio_stream]
        for buffer, output_streams in outputs.values():
            # Assign the packet to the new stream & mux
            if output_streams.get(audio_stream):
                packet.stream = output_streams[audio_stream]
                buffer.output.mux(packet)

    if not peek_first_pts():
        container.close()
        return
    last_dts = {k: v - 1 for k, v in first_pts.items()}
    initialize_segment(first_pts[video_stream])

    while not quit_event.is_set():
        try:
            if len(initial_packets) > 0:
                packet = initial_packets.popleft()
            else:
                packet = next(container.demux((video_stream, audio_stream)))
            if packet.dts is None:
                _LOGGER.error("Stream packet without dts detected, skipping...")
                # Allow a single packet without dts before terminating the stream.
                if last_packet_was_without_dts:
                    # If we get a "flushing" packet, the stream is done
                    raise StopIteration("No dts in consecutive packets")
                last_packet_was_without_dts = True
                continue
            last_packet_was_without_dts = False
        except (av.AVError, StopIteration) as ex:
            if not stream.keepalive:
                # End of stream, clear listeners and stop thread
                for fmt, _ in outputs.items():
                    hass.loop.call_soon_threadsafe(stream.outputs[fmt].put, None)
            _LOGGER.error("Error demuxing stream: %s", str(ex))
            break

        # Discard packet if dts is not monotonic
        if packet.dts <= last_dts[packet.stream]:
            continue

        # Check for end of segment
        if packet.stream == video_stream and packet.is_keyframe:
            segment_duration = (packet.pts - segment_start_pts) * packet.time_base
            if segment_duration >= MIN_SEGMENT_DURATION:
                # Save segment to outputs
                for fmt, (buffer, _) in outputs.items():
                    buffer.output.close()
                    if stream.outputs.get(fmt):
                        hass.loop.call_soon_threadsafe(
                            stream.outputs[fmt].put,
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
