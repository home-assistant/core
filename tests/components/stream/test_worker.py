"""Test the stream worker corner cases.

Exercise the stream worker functionality by mocking av.open calls to return a
fake media container as well a fake decoded stream in the form of a series of
packets. This is needed as some of these cases can't be encoded using pyav.  It
is preferred to use test_hls.py for example, when possible.

The worker opens the stream source (typically a URL) and gets back a
container that has audio/video streams. The worker iterates over the sequence
of packets and sends them to the appropriate output buffers. Each test
creates a packet sequence, with a mocked output buffer to capture the segments
pushed to the output streams. The packet sequence can be used to exercise
failure modes or corner cases like how out of order packets are handled.
"""
import asyncio
import fractions
import io
import logging
import math
from pathlib import Path
import threading
from unittest.mock import patch

import av
import numpy as np
import pytest

from homeassistant.components.stream import KeyFrameConverter, Stream, create_stream
from homeassistant.components.stream.const import (
    ATTR_SETTINGS,
    CONF_LL_HLS,
    CONF_PART_DURATION,
    CONF_SEGMENT_DURATION,
    DOMAIN,
    HLS_PROVIDER,
    MAX_MISSING_DTS,
    PACKETS_TO_WAIT_FOR_AUDIO,
    RECORDER_PROVIDER,
    SEGMENT_DURATION_ADJUSTER,
    TARGET_SEGMENT_DURATION_NON_LL_HLS,
)
from homeassistant.components.stream.core import Orientation, StreamSettings
from homeassistant.components.stream.worker import (
    StreamEndedError,
    StreamState,
    StreamWorkerError,
    stream_worker,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import dynamic_stream_settings, generate_h264_video, generate_h265_video
from .test_ll_hls import TEST_PART_DURATION

from tests.components.camera.common import EMPTY_8_6_JPEG, mock_turbo_jpeg

STREAM_SOURCE = "some-stream-source"
# Formats here are arbitrary, not exercised by tests
AUDIO_STREAM_FORMAT = "mp3"
VIDEO_STREAM_FORMAT = "h264"
VIDEO_FRAME_RATE = 12
VIDEO_TIME_BASE = fractions.Fraction(1 / 90000)
AUDIO_SAMPLE_RATE = 11025
KEYFRAME_INTERVAL = 1  # in seconds
PACKET_DURATION = fractions.Fraction(1, VIDEO_FRAME_RATE)  # in seconds
SEGMENT_DURATION = (
    math.ceil(TARGET_SEGMENT_DURATION_NON_LL_HLS / KEYFRAME_INTERVAL)
    * KEYFRAME_INTERVAL
)  # in seconds
TEST_SEQUENCE_LENGTH = 5 * VIDEO_FRAME_RATE
LONGER_TEST_SEQUENCE_LENGTH = 20 * VIDEO_FRAME_RATE
OUT_OF_ORDER_PACKET_INDEX = 3 * VIDEO_FRAME_RATE
PACKETS_PER_SEGMENT = SEGMENT_DURATION / PACKET_DURATION
SEGMENTS_PER_PACKET = PACKET_DURATION / SEGMENT_DURATION
TIMEOUT = 15


@pytest.fixture
def filename(tmp_path: Path) -> str:
    """Use this filename for the tests."""
    return str(tmp_path / "test.mp4")


@pytest.fixture(autouse=True)
def mock_stream_settings(hass):
    """Set the stream settings data in hass before each test."""
    hass.data[DOMAIN] = {
        ATTR_SETTINGS: StreamSettings(
            ll_hls=False,
            min_segment_duration=TARGET_SEGMENT_DURATION_NON_LL_HLS
            - SEGMENT_DURATION_ADJUSTER,
            part_target_duration=TARGET_SEGMENT_DURATION_NON_LL_HLS,
            hls_advance_part_limit=3,
            hls_part_timeout=TARGET_SEGMENT_DURATION_NON_LL_HLS,
        )
    }


class FakeAvInputStream:
    """A fake pyav Stream."""

    def __init__(self, name, time_base):
        """Initialize the stream."""
        self.name = name
        self.time_base = time_base
        self.profile = "ignored-profile"

        class FakeCodec:
            name = "aac"

        self.codec = FakeCodec()

        class FakeCodecContext:
            name = "h264"
            extradata = None

        self.codec_context = FakeCodecContext()

    @property
    def type(self):
        """Return packet type."""
        return "video" if self.name == VIDEO_STREAM_FORMAT else "audio"

    def __str__(self) -> str:
        """Return a stream name for debugging."""
        return f"FakePyAvStream<{self.name}, {self.time_base}>"


VIDEO_STREAM = FakeAvInputStream(VIDEO_STREAM_FORMAT, VIDEO_TIME_BASE)
AUDIO_STREAM = FakeAvInputStream(
    AUDIO_STREAM_FORMAT, fractions.Fraction(1 / AUDIO_SAMPLE_RATE)
)


class PacketSequence:
    """Creates packets in a sequence for exercising stream worker behavior.

    A test can create a PacketSequence(N) that will raise a StopIteration after
    N packets.  Each packet has an arbitrary monotomically increasing dts/pts value
    that is parseable by the worker, but a test can manipulate the values to
    exercise corner cases.
    """

    def __init__(self, num_packets):
        """Initialize the sequence with the number of packets it provides."""
        self.packet = 0
        self.num_packets = num_packets

    def __iter__(self):
        """Reset the sequence."""
        self.packet = 0
        return self

    def __next__(self):
        """Return the next packet."""
        if self.packet >= self.num_packets:
            raise StopIteration
        self.packet += 1

        class FakePacket(bytearray):
            # Be a bytearray so that memoryview works
            def __init__(self):
                super().__init__(3)

            time_base = VIDEO_TIME_BASE
            dts = round(self.packet * PACKET_DURATION / time_base)
            pts = round(self.packet * PACKET_DURATION / time_base)
            duration = round(PACKET_DURATION / time_base)
            stream = VIDEO_STREAM
            # Pretend we get 1 keyframe every second
            is_keyframe = not (self.packet - 1) % (VIDEO_FRAME_RATE * KEYFRAME_INTERVAL)
            size = 3

            def __str__(self) -> str:
                return f"FakePacket<stream={self.stream}, pts={self.pts}, key={self.is_keyframe}>"

        return FakePacket()


class FakePyAvContainer:
    """A fake container returned by mock av.open for a stream."""

    def __init__(self, video_stream, audio_stream):
        """Initialize the fake container."""
        # Tests can override this to trigger different worker behavior
        self.packets = PacketSequence(0)

        class FakePyAvStreams:
            video = [video_stream] if video_stream else []
            audio = [audio_stream] if audio_stream else []

        self.streams = FakePyAvStreams()

        class FakePyAvFormat:
            name = "ignored-format"

        self.format = FakePyAvFormat()

    def demux(self, streams):
        """Decode the streams from container, and return a packet sequence."""
        return self.packets

    def close(self):
        """Close the container."""
        return


class FakePyAvBuffer:
    """Holds outputs of the decoded stream for tests to assert on results."""

    def __init__(self):
        """Initialize the FakePyAvBuffer."""
        self.segments = []
        self.audio_packets = []
        self.video_packets = []
        self.memory_file: io.BytesIO | None = None

    def add_stream(self, template=None):
        """Create an output buffer that captures packets for test to examine."""

        class FakeAvOutputStream:
            def __init__(self, capture_packets):
                self.capture_packets = capture_packets
                self.type = "ignored-type"

            def close(self):
                return

            def mux(self, packet):
                logging.debug("Muxed packet: %s", packet)
                self.capture_packets.append(packet)

            def __str__(self) -> str:
                return f"FakeAvOutputStream<{template.name}>"

            def name(self) -> str:
                return "avc1"

        if template.name == AUDIO_STREAM_FORMAT:
            return FakeAvOutputStream(self.audio_packets)
        return FakeAvOutputStream(self.video_packets)

    def mux(self, packet):
        """Capture a packet for tests to examine."""
        # Forward to appropriate FakeStream
        packet.stream.mux(packet)
        # Make new init/part data available to the worker
        self.memory_file.write(b"\x00\x00\x00\x08moov")

    def close(self):
        """Close the buffer."""
        # Make the final segment data available to the worker
        self.memory_file.write(b"0")

    def capture_output_segment(self, segment):
        """Capture the output segment for tests to inspect."""
        self.segments.append(segment)

    @property
    def complete_segments(self):
        """Return only the complete segments."""
        return [segment for segment in self.segments if segment.complete]


class MockPyAv:
    """Mocks out av.open."""

    def __init__(self, video=True, audio=False):
        """Initialize the MockPyAv."""
        video_stream = VIDEO_STREAM if video else None
        audio_stream = AUDIO_STREAM if audio else None
        self.container = FakePyAvContainer(
            video_stream=video_stream, audio_stream=audio_stream
        )
        self.capture_buffer = FakePyAvBuffer()

    def open(self, stream_source, *args, **kwargs):
        """Return a stream or buffer depending on args."""
        if isinstance(stream_source, io.BytesIO):
            self.capture_buffer.memory_file = stream_source
            return self.capture_buffer
        return self.container


def run_worker(hass, stream, stream_source, stream_settings=None):
    """Run the stream worker under test."""
    stream_state = StreamState(hass, stream.outputs, stream._diagnostics)
    stream_worker(
        stream_source,
        {},
        stream_settings or hass.data[DOMAIN][ATTR_SETTINGS],
        stream_state,
        KeyFrameConverter(hass, stream_settings, dynamic_stream_settings()),
        threading.Event(),
    )


async def async_decode_stream(hass, packets, py_av=None, stream_settings=None):
    """Start a stream worker that decodes incoming stream packets into output segments."""
    stream = Stream(
        hass,
        STREAM_SOURCE,
        {},
        stream_settings or hass.data[DOMAIN][ATTR_SETTINGS],
        dynamic_stream_settings(),
    )
    stream.add_provider(HLS_PROVIDER)

    if not py_av:
        py_av = MockPyAv()
    py_av.container.packets = iter(packets)  # Can't be rewound

    with patch("av.open", new=py_av.open), patch(
        "homeassistant.components.stream.core.StreamOutput.put",
        side_effect=py_av.capture_buffer.capture_output_segment,
    ):
        try:
            run_worker(hass, stream, STREAM_SOURCE, stream_settings)
        except StreamEndedError:
            # Tests only use a limited number of packets, then the worker exits as expected. In
            # production, stream ending would be unexpected.
            pass
        finally:
            # Wait for all packets to be flushed even when exceptions are thrown
            await hass.async_block_till_done()

    return py_av.capture_buffer


async def test_stream_open_fails(hass: HomeAssistant) -> None:
    """Test failure on stream open."""
    stream = Stream(
        hass,
        STREAM_SOURCE,
        {},
        hass.data[DOMAIN][ATTR_SETTINGS],
        dynamic_stream_settings(),
    )
    stream.add_provider(HLS_PROVIDER)
    with patch("av.open") as av_open, pytest.raises(StreamWorkerError):
        av_open.side_effect = av.error.InvalidDataError(-2, "error")
        run_worker(hass, stream, STREAM_SOURCE)
        await hass.async_block_till_done()
        av_open.assert_called_once()


async def test_stream_worker_success(hass: HomeAssistant) -> None:
    """Test a short stream that ends and outputs everything correctly."""
    decoded_stream = await async_decode_stream(
        hass, PacketSequence(TEST_SEQUENCE_LENGTH)
    )
    segments = decoded_stream.segments
    complete_segments = decoded_stream.complete_segments
    # Check number of segments. A segment is only formed when a packet from the next
    # segment arrives, hence the subtraction of one from the sequence length.
    assert len(complete_segments) == int(
        (TEST_SEQUENCE_LENGTH - 1) * SEGMENTS_PER_PACKET
    )
    # Check sequence numbers
    assert all(segments[i].sequence == i for i in range(len(segments)))
    # Check segment durations
    assert all(s.duration == SEGMENT_DURATION for s in complete_segments)
    assert len(decoded_stream.video_packets) == TEST_SEQUENCE_LENGTH
    assert len(decoded_stream.audio_packets) == 0


async def test_skip_out_of_order_packet(hass: HomeAssistant) -> None:
    """Skip a single out of order packet."""
    packets = list(PacketSequence(TEST_SEQUENCE_LENGTH))
    # for this test, make sure the out of order index doesn't happen on a keyframe
    out_of_order_index = OUT_OF_ORDER_PACKET_INDEX
    if packets[out_of_order_index].is_keyframe:
        out_of_order_index += 1
    # This packet is out of order
    assert not packets[out_of_order_index].is_keyframe
    packets[out_of_order_index].dts = -9090

    decoded_stream = await async_decode_stream(hass, packets)
    segments = decoded_stream.segments
    complete_segments = decoded_stream.complete_segments
    # Check sequence numbers
    assert all(segments[i].sequence == i for i in range(len(segments)))
    # If skipped packet would have been the first packet of a segment, the previous
    # segment will be longer by a packet duration
    # We also may possibly lose a segment due to the shifting pts boundary
    if out_of_order_index % PACKETS_PER_SEGMENT == 0:
        # Check duration of affected segment and remove it
        longer_segment_index = int((out_of_order_index - 1) * SEGMENTS_PER_PACKET)
        assert (
            segments[longer_segment_index].duration
            == SEGMENT_DURATION + PACKET_DURATION
        )
        del segments[longer_segment_index]
        # Check number of segments
        assert len(complete_segments) == int(
            (len(packets) - 1 - 1) * SEGMENTS_PER_PACKET - 1
        )
    else:  # Otherwise segment durations and number of segments are unaffected
        # Check number of segments
        assert len(complete_segments) == int((len(packets) - 1) * SEGMENTS_PER_PACKET)
    # Check remaining segment durations
    assert all(s.duration == SEGMENT_DURATION for s in complete_segments)
    assert len(decoded_stream.video_packets) == len(packets) - 1
    assert len(decoded_stream.audio_packets) == 0


async def test_discard_old_packets(hass: HomeAssistant) -> None:
    """Skip a series of out of order packets."""

    packets = list(PacketSequence(TEST_SEQUENCE_LENGTH))
    # Packets after this one are considered out of order
    packets[OUT_OF_ORDER_PACKET_INDEX - 1].dts = round(
        TEST_SEQUENCE_LENGTH / VIDEO_FRAME_RATE / VIDEO_TIME_BASE
    )

    decoded_stream = await async_decode_stream(hass, packets)
    segments = decoded_stream.segments
    complete_segments = decoded_stream.complete_segments
    # Check number of segments
    assert len(complete_segments) == int(
        (OUT_OF_ORDER_PACKET_INDEX - 1) * SEGMENTS_PER_PACKET
    )
    # Check sequence numbers
    assert all(segments[i].sequence == i for i in range(len(segments)))
    # Check segment durations
    assert all(s.duration == SEGMENT_DURATION for s in complete_segments)
    assert len(decoded_stream.video_packets) == OUT_OF_ORDER_PACKET_INDEX
    assert len(decoded_stream.audio_packets) == 0


async def test_packet_overflow(hass: HomeAssistant) -> None:
    """Packet is too far out of order, and looks like overflow, ending stream early."""

    packets = list(PacketSequence(TEST_SEQUENCE_LENGTH))
    # Packet is so far out of order, exceeds max gap and looks like overflow
    packets[OUT_OF_ORDER_PACKET_INDEX].dts = -9000000

    py_av = MockPyAv()
    with pytest.raises(StreamWorkerError, match=r"Timestamp discontinuity detected"):
        await async_decode_stream(hass, packets, py_av=py_av)
    decoded_stream = py_av.capture_buffer
    segments = decoded_stream.segments
    complete_segments = decoded_stream.complete_segments
    # Check number of segments
    assert len(complete_segments) == int(
        (OUT_OF_ORDER_PACKET_INDEX - 1) * SEGMENTS_PER_PACKET
    )
    # Check sequence numbers
    assert all(segments[i].sequence == i for i in range(len(segments)))
    # Check segment durations
    assert all(s.duration == SEGMENT_DURATION for s in complete_segments)
    assert len(decoded_stream.video_packets) == OUT_OF_ORDER_PACKET_INDEX
    assert len(decoded_stream.audio_packets) == 0


async def test_skip_initial_bad_packets(hass: HomeAssistant) -> None:
    """Tests a small number of initial "bad" packets with missing dts."""

    num_packets = LONGER_TEST_SEQUENCE_LENGTH
    packets = list(PacketSequence(num_packets))
    num_bad_packets = MAX_MISSING_DTS - 1
    for i in range(0, num_bad_packets):
        packets[i].dts = None

    decoded_stream = await async_decode_stream(hass, packets)
    segments = decoded_stream.segments
    complete_segments = decoded_stream.complete_segments
    # Check sequence numbers
    assert all(segments[i].sequence == i for i in range(len(segments)))
    # Check segment durations
    assert all(s.duration == SEGMENT_DURATION for s in complete_segments)
    assert (
        len(decoded_stream.video_packets)
        == num_packets
        - math.ceil(num_bad_packets / (VIDEO_FRAME_RATE * KEYFRAME_INTERVAL))
        * VIDEO_FRAME_RATE
        * KEYFRAME_INTERVAL
    )
    # Check number of segments
    assert len(complete_segments) == int(
        (len(decoded_stream.video_packets) - 1) * SEGMENTS_PER_PACKET
    )
    assert len(decoded_stream.audio_packets) == 0


async def test_too_many_initial_bad_packets_fails(hass: HomeAssistant) -> None:
    """Test initial bad packets are too high, causing it to never start."""

    num_packets = LONGER_TEST_SEQUENCE_LENGTH
    packets = list(PacketSequence(num_packets))
    num_bad_packets = MAX_MISSING_DTS + 1
    for i in range(0, num_bad_packets):
        packets[i].dts = None

    py_av = MockPyAv()
    with pytest.raises(StreamWorkerError, match=r"No dts"):
        await async_decode_stream(hass, packets, py_av=py_av)
    decoded_stream = py_av.capture_buffer
    segments = decoded_stream.segments
    assert len(segments) == 0
    assert len(decoded_stream.video_packets) == 0
    assert len(decoded_stream.audio_packets) == 0


async def test_skip_missing_dts(hass: HomeAssistant) -> None:
    """Test packets in the middle of the stream missing DTS are skipped."""

    num_packets = LONGER_TEST_SEQUENCE_LENGTH
    packets = list(PacketSequence(num_packets))
    bad_packet_start = int(LONGER_TEST_SEQUENCE_LENGTH / 2)
    num_bad_packets = MAX_MISSING_DTS - 1
    for i in range(bad_packet_start, bad_packet_start + num_bad_packets):
        if packets[i].is_keyframe:
            num_bad_packets -= 1
            continue
        packets[i].dts = None

    decoded_stream = await async_decode_stream(hass, packets)
    segments = decoded_stream.segments
    complete_segments = decoded_stream.complete_segments
    # Check sequence numbers
    assert all(segments[i].sequence == i for i in range(len(segments)))
    # Check segment durations (not counting the last segment)
    assert sum(segment.duration for segment in complete_segments) >= len(segments) - 1
    assert len(decoded_stream.video_packets) == num_packets - num_bad_packets
    assert len(decoded_stream.audio_packets) == 0


async def test_too_many_bad_packets(hass: HomeAssistant) -> None:
    """Test bad packets are too many, causing it to end."""

    num_packets = LONGER_TEST_SEQUENCE_LENGTH
    packets = list(PacketSequence(num_packets))
    bad_packet_start = int(LONGER_TEST_SEQUENCE_LENGTH / 2)
    num_bad_packets = MAX_MISSING_DTS + 1
    for i in range(bad_packet_start, bad_packet_start + num_bad_packets):
        packets[i].dts = None

    py_av = MockPyAv()
    with pytest.raises(StreamWorkerError, match=r"No dts"):
        await async_decode_stream(hass, packets, py_av=py_av)
    decoded_stream = py_av.capture_buffer
    complete_segments = decoded_stream.complete_segments
    assert len(complete_segments) == int((bad_packet_start - 1) * SEGMENTS_PER_PACKET)
    assert len(decoded_stream.video_packets) == bad_packet_start
    assert len(decoded_stream.audio_packets) == 0


async def test_no_video_stream(hass: HomeAssistant) -> None:
    """Test no video stream in the container means no resulting output."""
    py_av = MockPyAv(video=False)

    with pytest.raises(StreamWorkerError, match=r"Stream has no video"):
        await async_decode_stream(
            hass, PacketSequence(TEST_SEQUENCE_LENGTH), py_av=py_av
        )
    decoded_stream = py_av.capture_buffer
    # Note: This failure scenario does not output an end of stream
    segments = decoded_stream.segments
    assert len(segments) == 0
    assert len(decoded_stream.video_packets) == 0
    assert len(decoded_stream.audio_packets) == 0


async def test_audio_packets_not_found(hass: HomeAssistant) -> None:
    """Set up an audio stream, but no audio packets are found."""
    py_av = MockPyAv(audio=True)

    num_packets = PACKETS_TO_WAIT_FOR_AUDIO + 1
    packets = PacketSequence(num_packets)  # Contains only video packets

    decoded_stream = await async_decode_stream(hass, packets, py_av=py_av)
    complete_segments = decoded_stream.complete_segments
    assert len(complete_segments) == int((num_packets - 1) * SEGMENTS_PER_PACKET)
    assert len(decoded_stream.video_packets) == num_packets
    assert len(decoded_stream.audio_packets) == 0


async def test_audio_is_first_packet(hass: HomeAssistant) -> None:
    """Set up an audio stream and audio packet is the first packet in the stream."""
    py_av = MockPyAv(audio=True)

    num_packets = PACKETS_TO_WAIT_FOR_AUDIO + 1
    packets = list(PacketSequence(num_packets))
    # Pair up an audio packet for each video packet
    packets[0].stream = AUDIO_STREAM
    packets[0].dts = round(packets[1].dts * VIDEO_TIME_BASE * AUDIO_SAMPLE_RATE)
    packets[0].pts = round(packets[1].pts * VIDEO_TIME_BASE * AUDIO_SAMPLE_RATE)
    packets[1].is_keyframe = True  # Move the video keyframe from packet 0 to packet 1
    packets[2].stream = AUDIO_STREAM
    packets[2].dts = round(packets[3].dts * VIDEO_TIME_BASE * AUDIO_SAMPLE_RATE)
    packets[2].pts = round(packets[3].pts * VIDEO_TIME_BASE * AUDIO_SAMPLE_RATE)

    decoded_stream = await async_decode_stream(hass, packets, py_av=py_av)
    complete_segments = decoded_stream.complete_segments
    # The audio packets are segmented with the video packets
    assert len(complete_segments) == int((num_packets - 2 - 1) * SEGMENTS_PER_PACKET)
    assert len(decoded_stream.video_packets) == num_packets - 2
    assert len(decoded_stream.audio_packets) == 1


async def test_audio_packets_found(hass: HomeAssistant) -> None:
    """Set up an audio stream and audio packets are found at the start of the stream."""
    py_av = MockPyAv(audio=True)

    num_packets = PACKETS_TO_WAIT_FOR_AUDIO + 1
    packets = list(PacketSequence(num_packets))
    packets[1].stream = AUDIO_STREAM
    packets[1].dts = round(packets[0].dts * VIDEO_TIME_BASE * AUDIO_SAMPLE_RATE)
    packets[1].pts = round(packets[0].pts * VIDEO_TIME_BASE * AUDIO_SAMPLE_RATE)

    decoded_stream = await async_decode_stream(hass, packets, py_av=py_av)
    complete_segments = decoded_stream.complete_segments
    # The audio packet above is buffered with the video packet
    assert len(complete_segments) == int((num_packets - 1 - 1) * SEGMENTS_PER_PACKET)
    assert len(decoded_stream.video_packets) == num_packets - 1
    assert len(decoded_stream.audio_packets) == 1


async def test_pts_out_of_order(hass: HomeAssistant) -> None:
    """Test pts can be out of order and still be valid."""

    # Create a sequence of packets with some out of order pts
    packets = list(PacketSequence(TEST_SEQUENCE_LENGTH))
    for i, _ in enumerate(packets):
        if i % PACKETS_PER_SEGMENT == 1:
            packets[i].pts = packets[i - 1].pts - 1
            packets[i].is_keyframe = False

    decoded_stream = await async_decode_stream(hass, packets)
    segments = decoded_stream.segments
    complete_segments = decoded_stream.complete_segments
    # Check number of segments
    assert len(complete_segments) == int(
        (TEST_SEQUENCE_LENGTH - 1) * SEGMENTS_PER_PACKET
    )
    # Check sequence numbers
    assert all(segments[i].sequence == i for i in range(len(segments)))
    # Check segment durations
    assert all(s.duration == SEGMENT_DURATION for s in complete_segments)
    assert len(decoded_stream.video_packets) == len(packets)
    assert len(decoded_stream.audio_packets) == 0


async def test_stream_stopped_while_decoding(hass: HomeAssistant) -> None:
    """Tests that worker quits when stop() is called while decodign."""
    # Add some synchronization so that the test can pause the background
    # worker. When the worker is stopped, the test invokes stop() which
    # will cause the worker thread to exit once it enters the decode
    # loop
    worker_open = threading.Event()
    worker_wake = threading.Event()

    stream = Stream(
        hass,
        STREAM_SOURCE,
        {},
        hass.data[DOMAIN][ATTR_SETTINGS],
        dynamic_stream_settings(),
    )
    stream.add_provider(HLS_PROVIDER)

    py_av = MockPyAv()
    py_av.container.packets = PacketSequence(TEST_SEQUENCE_LENGTH)

    def blocking_open(stream_source, *args, **kwargs):
        # Let test know the thread is running
        worker_open.set()
        # Block worker thread until test wakes up
        worker_wake.wait()
        return py_av.open(stream_source, args, kwargs)

    with patch("av.open", new=blocking_open):
        await stream.start()
        assert worker_open.wait(TIMEOUT)
        # Note: There is a race here where the worker could start as soon
        # as the wake event is sent, completing all decode work.
        worker_wake.set()
        await stream.stop()

    # Stream is still considered available when the worker was still active and asked to stop
    assert stream.available


async def test_update_stream_source(hass: HomeAssistant) -> None:
    """Tests that the worker is re-invoked when the stream source is updated."""
    worker_open = threading.Event()
    worker_wake = threading.Event()

    stream = Stream(
        hass,
        STREAM_SOURCE,
        {},
        hass.data[DOMAIN][ATTR_SETTINGS],
        dynamic_stream_settings(),
    )
    stream.add_provider(HLS_PROVIDER)
    # Note that retries are disabled by default in tests, however the stream is "restarted" when
    # the stream source is updated.

    py_av = MockPyAv()
    py_av.container.packets = PacketSequence(TEST_SEQUENCE_LENGTH)

    last_stream_source = None

    def blocking_open(stream_source, *args, **kwargs):
        nonlocal last_stream_source
        if not isinstance(stream_source, io.BytesIO):
            last_stream_source = stream_source
            # Let test know the thread is running
            worker_open.set()
            # Block worker thread until test wakes up
            worker_wake.wait()
        return py_av.open(stream_source, args, kwargs)

    with patch("av.open", new=blocking_open):
        await stream.start()
        assert worker_open.wait(TIMEOUT)
        assert last_stream_source == STREAM_SOURCE
        assert stream.available

        # Update the stream source, then the test wakes up the worker and assert
        # that it re-opens the new stream (the test again waits on thread_started)
        worker_open.clear()
        stream.update_source(STREAM_SOURCE + "-updated-source")
        worker_wake.set()
        assert worker_open.wait(TIMEOUT)
        assert last_stream_source == STREAM_SOURCE + "-updated-source"
        worker_wake.set()
        assert stream.available

        # Cleanup
        await stream.stop()


test_worker_log_cases = (
    ("https://abcd:efgh@foo.bar", "https://****:****@foo.bar"),
    (
        "https://foo.bar/baz?user=abcd&password=efgh",
        "https://foo.bar/baz?user=****&password=****",
    ),
    (
        "https://foo.bar/baz?param1=abcd&param2=efgh",
        "https://foo.bar/baz?param1=abcd&param2=efgh",
    ),
    (
        "https://foo.bar/baz?param1=abcd&password=efgh",
        "https://foo.bar/baz?param1=abcd&password=****",
    ),
)


@pytest.mark.parametrize(("stream_url", "redacted_url"), test_worker_log_cases)
async def test_worker_log(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, stream_url, redacted_url
) -> None:
    """Test that the worker logs the url without username and password."""
    stream = Stream(
        hass,
        stream_url,
        {},
        hass.data[DOMAIN][ATTR_SETTINGS],
        dynamic_stream_settings(),
    )
    stream.add_provider(HLS_PROVIDER)

    with patch("av.open") as av_open, pytest.raises(StreamWorkerError) as err:
        av_open.side_effect = av.error.InvalidDataError(-2, "error")
        run_worker(hass, stream, stream_url)
        await hass.async_block_till_done()
    assert (
        str(err.value) == f"Error opening stream (ERRORTYPE_-2, error) {redacted_url}"
    )
    assert stream_url not in caplog.text


@pytest.fixture
def worker_finished_stream():
    """Fixture that helps call a stream and wait for the worker to finish."""
    worker_finished = asyncio.Event()

    class MockStream(Stream):
        """Mock Stream so we can patch remove_provider."""

        async def remove_provider(self, provider):
            """Add a finished event to Stream.remove_provider."""
            await Stream.remove_provider(self, provider)
            worker_finished.set()

    return worker_finished, MockStream


async def test_durations(hass: HomeAssistant, worker_finished_stream) -> None:
    """Test that the duration metadata matches the media."""

    # Use a target part duration which has a slight mismatch
    # with the incoming frame rate to better expose problems.
    target_part_duration = TEST_PART_DURATION - 0.01
    await async_setup_component(
        hass,
        "stream",
        {
            "stream": {
                CONF_LL_HLS: True,
                CONF_SEGMENT_DURATION: SEGMENT_DURATION,
                CONF_PART_DURATION: target_part_duration,
            }
        },
    )

    source = generate_h264_video(
        duration=round(SEGMENT_DURATION + target_part_duration + 1)
    )
    worker_finished, mock_stream = worker_finished_stream

    with patch("homeassistant.components.stream.Stream", wraps=mock_stream):
        stream = create_stream(
            hass, source, {}, dynamic_stream_settings(), stream_label="camera"
        )

    recorder_output = stream.add_provider(RECORDER_PROVIDER, timeout=30)
    await stream.start()
    await worker_finished.wait()

    complete_segments = list(recorder_output.get_segments())[:-1]

    assert len(complete_segments) >= 1

    # check that the Part duration metadata matches the durations in the media
    running_metadata_duration = 0
    for segment in complete_segments:
        av_segment = av.open(io.BytesIO(segment.init + segment.get_data()))
        av_segment.close()
        for part_num, part in enumerate(segment.parts):
            av_part = av.open(io.BytesIO(segment.init + part.data))
            running_metadata_duration += part.duration
            # av_part.duration actually returns the dts of the first packet of the next
            # av_part. When we normalize this by av.time_base we get the running
            # duration of the media.
            # The metadata duration may differ slightly from the media duration.
            # The worker has some flexibility of where to set each metadata boundary,
            # and when the media's duration is slightly too long or too short, the
            # metadata duration may be adjusted up or down.
            # We check here that the divergence between the metadata duration and the
            # media duration is not too large (2 frames seems reasonable here).
            assert math.isclose(
                (av_part.duration - av_part.start_time) / av.time_base,
                part.duration,
                abs_tol=2 / av_part.streams.video[0].average_rate + 1e-6,
            )
            # Also check that the sum of the durations so far matches the last dts
            # in the media.
            assert math.isclose(
                running_metadata_duration,
                av_part.duration / av.time_base,
                abs_tol=1e-6,
            )
            # And check that the metadata duration is between 0.85x and 1.0x of
            # the part target duration
            if not (part.has_keyframe or part_num == len(segment.parts) - 1):
                assert part.duration > 0.85 * target_part_duration - 1e-6
            assert part.duration < target_part_duration + 1e-6
            av_part.close()
    # check that the Part durations are consistent with the Segment durations
    for segment in complete_segments:
        assert math.isclose(
            sum(part.duration for part in segment.parts),
            segment.duration,
            abs_tol=1e-6,
        )

    await stream.stop()


async def test_has_keyframe(
    hass: HomeAssistant, h264_video, worker_finished_stream
) -> None:
    """Test that the has_keyframe metadata matches the media."""
    await async_setup_component(
        hass,
        "stream",
        {
            "stream": {
                CONF_LL_HLS: True,
                CONF_SEGMENT_DURATION: SEGMENT_DURATION,
                # Our test video has keyframes every second. Use smaller parts so we have more
                # part boundaries to better test keyframe logic.
                CONF_PART_DURATION: 0.25,
            }
        },
    )

    worker_finished, mock_stream = worker_finished_stream

    with patch("homeassistant.components.stream.Stream", wraps=mock_stream):
        stream = create_stream(
            hass, h264_video, {}, dynamic_stream_settings(), stream_label="camera"
        )

    recorder_output = stream.add_provider(RECORDER_PROVIDER, timeout=30)
    await stream.start()
    await worker_finished.wait()

    complete_segments = list(recorder_output.get_segments())[:-1]

    assert len(complete_segments) >= 1

    # check that the Part has_keyframe metadata matches the keyframes in the media
    for segment in complete_segments:
        for part in segment.parts:
            av_part = av.open(io.BytesIO(segment.init + part.data))
            media_has_keyframe = any(
                packet.is_keyframe for packet in av_part.demux(av_part.streams.video[0])
            )
            av_part.close()
            assert part.has_keyframe == media_has_keyframe

    await stream.stop()


async def test_h265_video_is_hvc1(hass: HomeAssistant, worker_finished_stream) -> None:
    """Test that a h265 video gets muxed as hvc1."""
    await async_setup_component(
        hass,
        "stream",
        {
            "stream": {
                CONF_LL_HLS: True,
                CONF_SEGMENT_DURATION: SEGMENT_DURATION,
                CONF_PART_DURATION: TEST_PART_DURATION,
            }
        },
    )

    source = generate_h265_video()

    worker_finished, mock_stream = worker_finished_stream
    with patch("homeassistant.components.stream.Stream", wraps=mock_stream):
        stream = create_stream(
            hass, source, {}, dynamic_stream_settings(), stream_label="camera"
        )

    recorder_output = stream.add_provider(RECORDER_PROVIDER, timeout=30)
    await stream.start()
    await worker_finished.wait()

    complete_segments = list(recorder_output.get_segments())[:-1]
    assert len(complete_segments) >= 1

    segment = complete_segments[0]
    part = segment.parts[0]
    av_part = av.open(io.BytesIO(segment.init + part.data))
    assert av_part.streams.video[0].codec_tag == "hvc1"
    av_part.close()

    await stream.stop()

    assert stream.get_diagnostics() == {
        "container_format": "mov,mp4,m4a,3gp,3g2,mj2",
        "keepalive": False,
        "orientation": Orientation.NO_TRANSFORM,
        "start_worker": 1,
        "video_codec": "hevc",
        "worker_error": 1,
    }


async def test_get_image(hass: HomeAssistant, h264_video, filename) -> None:
    """Test that the has_keyframe metadata matches the media."""
    await async_setup_component(hass, "stream", {"stream": {}})

    # Since libjpeg-turbo is not installed on the CI runner, we use a mock
    with patch(
        "homeassistant.components.camera.img_util.TurboJPEGSingleton"
    ) as mock_turbo_jpeg_singleton:
        mock_turbo_jpeg_singleton.instance.return_value = mock_turbo_jpeg()
        stream = create_stream(hass, h264_video, {}, dynamic_stream_settings())

    with patch.object(hass.config, "is_allowed_path", return_value=True):
        make_recording = hass.async_create_task(stream.async_record(filename))
        await make_recording
    assert stream._keyframe_converter._image is None

    assert await stream.async_get_image() == EMPTY_8_6_JPEG

    await stream.stop()


async def test_worker_disable_ll_hls(hass: HomeAssistant) -> None:
    """Test that the worker disables ll-hls for hls inputs."""
    stream_settings = StreamSettings(
        ll_hls=True,
        min_segment_duration=TARGET_SEGMENT_DURATION_NON_LL_HLS
        - SEGMENT_DURATION_ADJUSTER,
        part_target_duration=TARGET_SEGMENT_DURATION_NON_LL_HLS,
        hls_advance_part_limit=3,
        hls_part_timeout=TARGET_SEGMENT_DURATION_NON_LL_HLS,
    )
    py_av = MockPyAv()
    py_av.container.format.name = "hls"
    await async_decode_stream(
        hass,
        PacketSequence(TEST_SEQUENCE_LENGTH),
        py_av=py_av,
        stream_settings=stream_settings,
    )
    assert stream_settings.ll_hls is False


async def test_get_image_rotated(hass: HomeAssistant, h264_video, filename) -> None:
    """Test that the has_keyframe metadata matches the media."""
    await async_setup_component(hass, "stream", {"stream": {}})

    # Since libjpeg-turbo is not installed on the CI runner, we use a mock
    with patch(
        "homeassistant.components.camera.img_util.TurboJPEGSingleton"
    ) as mock_turbo_jpeg_singleton:
        mock_turbo_jpeg_singleton.instance.return_value = mock_turbo_jpeg()
        for orientation in (Orientation.NO_TRANSFORM, Orientation.ROTATE_RIGHT):
            stream = create_stream(hass, h264_video, {}, dynamic_stream_settings())
            stream.dynamic_stream_settings.orientation = orientation

            with patch.object(hass.config, "is_allowed_path", return_value=True):
                make_recording = hass.async_create_task(stream.async_record(filename))
                await make_recording
            assert stream._keyframe_converter._image is None

            assert await stream.async_get_image() == EMPTY_8_6_JPEG
            await stream.stop()
        assert (
            np.rot90(
                mock_turbo_jpeg_singleton.instance.return_value.encode.call_args_list[
                    0
                ][0][0]
            )
            == mock_turbo_jpeg_singleton.instance.return_value.encode.call_args_list[1][
                0
            ][0]
        ).all()
