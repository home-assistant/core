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


class StreamWorker:
    """Worker that blocks and consumes a stream, populating output buffers.

    A StreamWorker opens a stream's source, decodes packets from the media
    container, and produces segments of audio/video which are written to
    output buffers.

    The StreamWorker manages the state needed at start (peeking into the stream
    and examining the first set of initial packets) and then muxing packets to
    output buffers as well as creation of segments every MIN_SEGMENT_DURATION
    seconds of media.

    The run method is blocking, and expected to be run from a callers worker
    thread.  The worker will run until either the end of the stream is reached
    or the quit_event signals the stream to exit.  The Steam's keepalive
    property enables retry on error, with backoff.
    """

    def __init__(self, hass, stream):
        """Initialize StreamWorker."""
        self._hass = hass
        self._stream = stream
        # Holds the buffers for each stream provider
        self._outputs = {}
        self._audio_stream = None
        self._video_stream = None
        # Keep track of the number of segments we've processed
        self._sequence = 0
        # The video pts at the beginning of the segment
        self._segment_start_pts = None
        # Store initial packets for replaying to workaround bad streams
        self._initial_packets = deque()
        self._container = None
        # Iterator for demuxing
        self._container_packets = None

    def run(self, quit_event):
        """Handle consuming streams and restart keepalive streams."""

        wait_timeout = 0
        while not quit_event.wait(timeout=wait_timeout):
            start_time = time.time()
            try:
                self._stream_worker_internal(quit_event)
            except av.error.FFmpegError:  # pylint: disable=c-extension-no-member
                _LOGGER.exception("Stream connection failed: %s", self._stream.source)
            if not self._stream.keepalive or quit_event.is_set():
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
                self._stream.source,
            )

    def _stream_worker_internal(self, quit_event):
        """Handle consuming streams."""

        try:
            self._container = av.open(
                self._stream.source,
                options=self._stream.options,
                timeout=STREAM_TIMEOUT,
            )
        except av.AVError:
            _LOGGER.error("Error opening stream %s", self._stream.source)
            return
        try:
            self._video_stream = self._container.streams.video[0]
        except (KeyError, IndexError):
            _LOGGER.error("Stream has no video")
            self._container.close()
            return
        try:
            self._audio_stream = self._container.streams.audio[0]
        except (KeyError, IndexError):
            self._audio_stream = None
        # These formats need aac_adtstoasc bitstream filter, but auto_bsf not
        # compatible with empty_moov and manual bitstream filters not in PyAV
        if self._container.format.name in {"hls", "mpegts"}:
            self._audio_stream = None
        # Some audio streams do not have a profile and throw errors when remuxing
        if self._audio_stream and self._audio_stream.profile is None:
            self._audio_stream = None

        self._run_decode_loop(quit_event)

    # Have to work around two problems with RTSP feeds in ffmpeg
    # 1 - first frame has bad pts/dts https://trac.ffmpeg.org/ticket/5018
    # 2 - seeking can be problematic https://trac.ffmpeg.org/ticket/7815

    def _peek_first_pts(self):
        """Initialize by peeking into the first few packets of the stream.

        Deal with problem #1 above (bad first packet pts/dts) by recalculating using pts/dts from second packet.
        Also load the first video keyframe pts into segment_start_pts and check if the audio stream really exists.
        """
        missing_dts = 0
        found_audio = False
        try:
            self._container_packets = self._container.demux(
                (self._video_stream, self._audio_stream)
            )
            first_packet = None
            # Get to first video keyframe
            while first_packet is None:
                packet = next(self._container_packets)
                if (
                    packet.dts is None
                ):  # Allow MAX_MISSING_DTS packets with no dts, raise error on the next one
                    if missing_dts >= MAX_MISSING_DTS:
                        raise StopIteration(
                            f"Invalid data - got {MAX_MISSING_DTS+1} packets with missing DTS while initializing"
                        )
                    missing_dts += 1
                    continue
                if packet.stream == self._audio_stream:
                    found_audio = True
                elif packet.is_keyframe:  # video_keyframe
                    first_packet = packet
                    self._initial_packets.append(packet)
            # Get first_pts from subsequent frame to first keyframe
            while self._segment_start_pts is None or (
                self._audio_stream
                and not found_audio
                and len(self._initial_packets) < PACKETS_TO_WAIT_FOR_AUDIO
            ):
                packet = next(self._container_packets)
                if (
                    packet.dts is None
                ):  # Allow MAX_MISSING_DTS packet with no dts, raise error on the next one
                    if missing_dts >= MAX_MISSING_DTS:
                        raise StopIteration(
                            f"Invalid data - got {MAX_MISSING_DTS+1} packets with missing DTS while initializing"
                        )
                    missing_dts += 1
                    continue
                if packet.stream == self._audio_stream:
                    found_audio = True
                elif self._segment_start_pts is None:
                    # This is the second video frame to calculate first_pts from
                    self._segment_start_pts = packet.dts - packet.duration
                    first_packet.pts = self._segment_start_pts
                    first_packet.dts = self._segment_start_pts
                self._initial_packets.append(packet)
            if self._audio_stream and not found_audio:
                _LOGGER.warning(
                    "Audio stream not found"
                )  # Some streams declare an audio stream and never send any packets
                self._audio_stream = None

        except (av.AVError, StopIteration) as ex:
            _LOGGER.error(
                "Error demuxing stream while finding first packet: %s", str(ex)
            )
            self._finalize_stream()
            return False
        return True

    def _initialize_segment(self, video_pts):
        """Reset some variables and initialize outputs for each segment."""
        # Clear outputs and increment sequence
        self._outputs = {}
        self._sequence += 1
        self._segment_start_pts = video_pts
        for stream_output in self._stream.outputs.values():
            if self._video_stream.name not in stream_output.video_codecs:
                continue
            buffer = create_stream_buffer(
                stream_output, self._video_stream, self._audio_stream, self._sequence
            )
            self._outputs[stream_output.name] = (
                buffer,
                {
                    self._video_stream: buffer.vstream,
                    self._audio_stream: buffer.astream,
                },
            )

    def _mux_video_packet(self, packet):
        # mux packets to each buffer
        for buffer, output_streams in self._outputs.values():
            # Assign the packet to the new stream & mux
            packet.stream = output_streams[self._video_stream]
            buffer.output.mux(packet)

    def _mux_audio_packet(self, packet):
        # almost the same as muxing video but add extra check
        for buffer, output_streams in self._outputs.values():
            # Assign the packet to the new stream & mux
            if output_streams.get(self._audio_stream):
                packet.stream = output_streams[self._audio_stream]
                buffer.output.mux(packet)

    def _finalize_stream(self):
        if self._stream.keepalive:
            return
        # End of stream, clear listeners and stop thread
        for fmt in self._stream.outputs:
            self._hass.loop.call_soon_threadsafe(self._stream.outputs[fmt].put, None)

    def _run_decode_loop(self, quit_event):
        # Keep track of consecutive packets without a dts to detect end of stream.
        missing_dts = 0
        # The decoder timestamps of the latest packet in each stream we processed
        last_dts = {
            self._video_stream: float("-inf"),
            self._audio_stream: float("-inf"),
        }

        if not self._peek_first_pts():
            self._container.close()
            return

        self._initialize_segment(self._segment_start_pts)

        while not quit_event.is_set():
            try:
                if len(self._initial_packets) > 0:
                    packet = self._initial_packets.popleft()
                else:
                    packet = next(self._container_packets)
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
                self._finalize_stream()
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
                    self._finalize_stream()
                    break
                continue

            # Check for end of segment
            if packet.stream == self._video_stream and packet.is_keyframe:
                segment_duration = (
                    packet.pts - self._segment_start_pts
                ) * packet.time_base
                if segment_duration >= MIN_SEGMENT_DURATION:
                    # Save segment to outputs
                    for fmt, (buffer, _) in self._outputs.items():
                        buffer.output.close()
                        if self._stream.outputs.get(fmt):
                            self._hass.loop.call_soon_threadsafe(
                                self._stream.outputs[fmt].put,
                                Segment(
                                    self._sequence,
                                    buffer.segment,
                                    segment_duration,
                                ),
                            )

                    # Reinitialize
                    self._initialize_segment(packet.pts)

            # Update last_dts processed
            last_dts[packet.stream] = packet.dts
            # mux packets
            if packet.stream == self._video_stream:
                self._mux_video_packet(packet)  # mutates packet timestamps
            else:
                self._mux_audio_packet(packet)  # mutates packet timestamps

        # Close stream
        for buffer, _ in self._outputs.values():
            buffer.output.close()
        self._container.close()
