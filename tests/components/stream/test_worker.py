"""Test the stream worker.

Exercise the stream worker functionality by mocking av.open calls to return a
fake media container as well a fake decoded stream in the form of a series of
packets.

The worker opens the stream source (typically a URL) and gets back a
container that has audio/video streams.  The worker iterates over the sequence
of packets and sends them to the appropriate output buffers.  Each test
creates a packet sequence, with a mocked output buffer to capture the segments
pushed to the output streams.  The packet sequence can be used to exercise
failure modes or corner cases like how out of order packets are handled.
"""

import fractions
import threading

import av

from homeassistant.components.stream import Stream
from homeassistant.components.stream.const import (
    MAX_MISSING_DTS,
    PACKETS_TO_WAIT_FOR_AUDIO,
)
from homeassistant.components.stream.worker import stream_worker

from tests.async_mock import patch

STREAM_SOURCE = "some-stream-source"
# Formats here are arbitrary, not exercised by tests
STREAM_OUTPUT_FORMAT = "hls"
AUDIO_STREAM_FORMAT = "mp3"
VIDEO_STREAM_FORMAT = "h264"
PACKET_DURATION = 10


class FakePyAvStream:
    """A fake pyav Stream."""

    def __init__(self, name):
        """Initialize the stream."""
        self.name = name
        self.time_base = fractions.Fraction(1, 1)
        self.profile = "ignored-profile"


VIDEO_STREAM = FakePyAvStream(VIDEO_STREAM_FORMAT)
AUDIO_STREAM = FakePyAvStream(AUDIO_STREAM_FORMAT)


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

        class FakePacket:
            dts = self.packet * PACKET_DURATION
            pts = self.packet * PACKET_DURATION
            duration = PACKET_DURATION
            stream = VIDEO_STREAM
            is_keyframe = True
            time_base = fractions.Fraction(1, 1)

        return FakePacket()


class FakePyAvContainer:
    """A fake container returned by mock av.open for a stream."""

    def __init__(self, video_stream, audio_stream):
        """Initialize the fake container."""
        # Tests can override this to trigger different worker behavior
        self.packets = PacketSequence(0)

        class FakePyAvStreams:
            video = video_stream
            audio = audio_stream

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

    def add_stream(self, template=None):
        """Create an output buffer that captures packets for test to examine."""

        class FakeStream:
            def __init__(self, capture_packets):
                self.capture_packets = capture_packets

            def close(self):
                return

            def mux(self, packet):
                self.capture_packets.append(packet)

        if template.name == AUDIO_STREAM_FORMAT:
            return FakeStream(self.audio_packets)
        return FakeStream(self.video_packets)

    def mux(self, packet):
        """Capture a packet for tests to examine."""
        # Forward to appropriate FakeStream
        packet.stream.mux(packet)

    def close(self):
        """Close the buffer."""
        return

    def capture_output_segment(self, segment):
        """Capture the output segment for tests to inspect."""
        self.segments.append(segment)


class MockPyAv:
    """Mocks out av.open."""

    def __init__(self, video=True, audio=False):
        """Initialize the MockPyAv."""
        video_stream = [VIDEO_STREAM] if video else []
        audio_stream = [AUDIO_STREAM] if audio else []
        self.container = FakePyAvContainer(
            video_stream=video_stream, audio_stream=audio_stream
        )
        self.capture_buffer = FakePyAvBuffer()

    def open(self, stream_source, *args, **kwargs):
        """Return a stream or buffer depending on args."""
        if stream_source == STREAM_SOURCE:
            return self.container
        return self.capture_buffer


async def async_decode_stream(hass, packets, py_av=None):
    """Start a stream worker that decodes incoming stream packets into output segments."""
    stream = Stream(hass, STREAM_SOURCE)
    stream.add_provider(STREAM_OUTPUT_FORMAT)

    if not py_av:
        py_av = MockPyAv()
    py_av.container.packets = packets

    with patch("av.open", new=py_av.open), patch(
        "homeassistant.components.stream.core.StreamOutput.put",
        side_effect=py_av.capture_buffer.capture_output_segment,
    ):
        stream_worker(hass, stream, threading.Event())
        await hass.async_block_till_done()

    return py_av.capture_buffer


async def test_stream_open_fails(hass):
    """Test failure on stream open."""
    stream = Stream(hass, STREAM_SOURCE)
    stream.add_provider(STREAM_OUTPUT_FORMAT)
    with patch("av.open") as av_open:
        av_open.side_effect = av.error.InvalidDataError(-2, "error")
        stream_worker(hass, stream, threading.Event())
        await hass.async_block_till_done()
        av_open.assert_called_once()


async def test_stream_worker_success(hass):
    """Test a short stream that ends and outputs everything correctly."""

    decoded_stream = await async_decode_stream(hass, PacketSequence(5))
    segments = decoded_stream.segments
    assert len(segments) == 5
    assert segments[0].sequence == 1
    assert segments[0].duration == PACKET_DURATION
    assert segments[1].sequence == 2
    assert segments[1].duration == PACKET_DURATION
    assert segments[2].sequence == 3
    assert segments[2].duration == PACKET_DURATION
    assert segments[3].sequence == 4
    assert segments[3].duration == PACKET_DURATION
    assert segments[4] is None
    assert len(decoded_stream.video_packets) == 5
    assert len(decoded_stream.audio_packets) == 0


async def test_skip_out_of_order_packet(hass):
    """Skip a single out of order packet."""

    packets = list(PacketSequence(5))
    # This packet is out of order
    packets[2].dts = -9090

    decoded_stream = await async_decode_stream(hass, iter(packets))
    segments = decoded_stream.segments
    assert len(segments) == 4
    assert segments[0].sequence == 1
    assert segments[0].duration == PACKET_DURATION
    # Segment covers gap
    assert segments[1].sequence == 2
    assert segments[1].duration == 2 * PACKET_DURATION
    # Packet missing here
    assert segments[2].sequence == 3
    assert segments[2].duration == PACKET_DURATION
    assert segments[3] is None
    assert len(decoded_stream.video_packets) == 4
    assert len(decoded_stream.audio_packets) == 0


async def test_discard_old_packets(hass):
    """Skip a series of out of order packets."""

    packets = list(PacketSequence(5))
    # Packets after this one are considered out of order
    packets[2].dts = 9090

    decoded_stream = await async_decode_stream(hass, iter(packets))
    segments = decoded_stream.segments
    assert len(segments) == 3
    assert segments[0].sequence == 1
    assert segments[0].duration == PACKET_DURATION
    assert segments[1].sequence == 2
    assert segments[1].duration == PACKET_DURATION
    assert segments[2] is None
    assert len(decoded_stream.video_packets) == 3
    assert len(decoded_stream.audio_packets) == 0


async def test_packet_overflow(hass):
    """Packet is too far out of order, and looks like overflow, ending stream early."""

    packets = list(PacketSequence(5))
    # Packet is so far out of order, exceeds max gap and looks like overflow
    packets[2].dts = -9000000

    decoded_stream = await async_decode_stream(hass, iter(packets))
    segments = decoded_stream.segments
    assert len(segments) == 2
    assert segments[0].sequence == 1
    assert segments[0].duration == PACKET_DURATION
    assert segments[1] is None
    assert len(decoded_stream.video_packets) == 2
    assert len(decoded_stream.audio_packets) == 0


async def test_skip_initial_bad_packets(hass):
    """Tests a small number of initial missing bad packets."""

    num_packets = 20
    packets = list(PacketSequence(num_packets))
    num_bad_packets = MAX_MISSING_DTS - 1
    for i in range(0, num_bad_packets):
        packets[i].dts = None

    decoded_stream = await async_decode_stream(hass, iter(packets))
    segments = decoded_stream.segments
    assert len(segments) == num_packets - num_bad_packets
    assert len(decoded_stream.video_packets) == num_packets - num_bad_packets
    assert len(decoded_stream.audio_packets) == 0


async def test_too_many_initial_bad_packets_fails(hass):
    """Test initial bad packets are too high, causing it to never start."""

    num_packets = 20
    packets = list(PacketSequence(num_packets))
    num_bad_packets = MAX_MISSING_DTS + 1
    for i in range(0, num_bad_packets):
        packets[i].dts = None

    decoded_stream = await async_decode_stream(hass, iter(packets))
    segments = decoded_stream.segments
    assert len(segments) == 1
    assert segments[0] is None
    assert len(decoded_stream.video_packets) == 0
    assert len(decoded_stream.audio_packets) == 0


async def test_skip_missing_dts(hass):
    """Test packets in the middle of the stream missing DTS are skipped."""

    num_packets = 20
    packets = list(PacketSequence(num_packets))
    bad_packet_start = 10
    num_bad_packets = MAX_MISSING_DTS - 1
    for i in range(bad_packet_start, bad_packet_start + num_bad_packets):
        packets[i].dts = None

    decoded_stream = await async_decode_stream(hass, iter(packets))
    segments = decoded_stream.segments
    assert len(segments) == num_packets - num_bad_packets
    assert len(decoded_stream.video_packets) == num_packets - num_bad_packets
    assert len(decoded_stream.audio_packets) == 0


async def test_too_many_bad_packets(hass):
    """Test bad packets are too many, causing it to end."""

    num_packets = 20
    packets = list(PacketSequence(num_packets))
    bad_packet_start = 10
    num_bad_packets = MAX_MISSING_DTS + 1
    for i in range(bad_packet_start, bad_packet_start + num_bad_packets):
        packets[i].dts = None

    decoded_stream = await async_decode_stream(hass, iter(packets))
    segments = decoded_stream.segments
    assert len(segments) == bad_packet_start
    assert len(decoded_stream.video_packets) == bad_packet_start
    assert len(decoded_stream.audio_packets) == 0


async def test_no_video_stream(hass):
    """Test no video stream in the container means no resulting output."""
    py_av = MockPyAv(video=False)

    decoded_stream = await async_decode_stream(hass, PacketSequence(4), py_av=py_av)
    segments = decoded_stream.segments
    assert len(segments) == 0
    assert len(decoded_stream.video_packets) == 0
    assert len(decoded_stream.audio_packets) == 0


async def test_audio_packets_not_found(hass):
    """Set up an audio stream, but no audio packets are found."""
    py_av = MockPyAv(audio=True)

    num_packets = PACKETS_TO_WAIT_FOR_AUDIO + 5
    packets = PacketSequence(num_packets)  # Contains only video packets

    decoded_stream = await async_decode_stream(hass, iter(packets), py_av=py_av)
    segments = decoded_stream.segments
    assert len(segments) == num_packets
    assert len(decoded_stream.video_packets) == num_packets
    assert len(decoded_stream.audio_packets) == 0


async def test_audio_is_first_packet(hass):
    """Set up an audio stream and audio packet is the first packet in the stream."""
    py_av = MockPyAv(audio=True)

    num_packets = PACKETS_TO_WAIT_FOR_AUDIO + 5
    packets = list(PacketSequence(num_packets))
    # Pair up an audio packet for each video packet
    packets[0].stream = AUDIO_STREAM
    packets[0].dts = packets[1].dts
    packets[0].pts = packets[1].pts
    packets[2].stream = AUDIO_STREAM
    packets[2].dts = packets[3].dts
    packets[2].pts = packets[3].pts

    decoded_stream = await async_decode_stream(hass, iter(packets), py_av=py_av)
    segments = decoded_stream.segments
    # The audio packets are segmented with the video packets
    assert len(segments) == num_packets - 2
    assert len(decoded_stream.video_packets) == num_packets - 2
    assert len(decoded_stream.audio_packets) == 1


async def test_audio_packets_found(hass):
    """Set up an audio stream and audio packets are found at the start of the stream."""
    py_av = MockPyAv(audio=True)

    num_packets = PACKETS_TO_WAIT_FOR_AUDIO + 5
    packets = list(PacketSequence(num_packets))
    packets[1].stream = AUDIO_STREAM
    packets[1].dts = packets[0].dts
    packets[1].pts = packets[0].pts

    decoded_stream = await async_decode_stream(hass, iter(packets), py_av=py_av)
    segments = decoded_stream.segments
    # The audio packet above is buffered with the video packet
    assert len(segments) == num_packets - 1
    assert len(decoded_stream.video_packets) == 24
    assert len(decoded_stream.audio_packets) == 1
